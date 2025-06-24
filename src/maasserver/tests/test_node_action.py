# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json
import random
from unittest.mock import ANY, Mock

from django.db import transaction
from netaddr import IPNetwork
import pytest

from maascommon.events import AUDIT
from maasserver import locks
from maasserver.clusterrpc.utils import get_error_message_for_exception
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_ACTION_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    NODE_TYPE_CHOICES_DICT,
)
from maasserver.exceptions import NodeActionError
from maasserver.models import (
    Config,
    Event,
    Notification,
    ScriptSet,
    signals,
    StaticIPAddress,
)
from maasserver.models import node as node_module
from maasserver.models.signals.testing import SignalsDisabled
import maasserver.node_action as node_action_module
from maasserver.node_action import (
    Abort,
    Acquire,
    ACTION_CLASSES,
    AddTag,
    Clone,
    Commission,
    compile_node_actions,
    Delete,
    Deploy,
    ExitRescueMode,
    Lock,
    MarkBroken,
    MarkFixed,
    NodeAction,
    OverrideFailedTesting,
    PowerOff,
    PowerOn,
    Release,
    RemoveTag,
    RescueMode,
    RPC_EXCEPTIONS,
    SetPool,
    SetZone,
    Test,
    Unlock,
)
from maasserver.node_status import (
    MONITORED_STATUSES,
    NODE_TESTING_RESET_READY_TRANSITIONS,
    NON_MONITORED_STATUSES,
)
from maasserver.permissions import NodePermission
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import post_commit, post_commit_hooks, reload_object
from maastemporalworker.workflow import power as power_module
from metadataserver.builtin_scripts import load_builtin_scripts
from metadataserver.enum import (
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_FAILED,
    SCRIPT_TYPE,
)
from provisioningserver.enum import POWER_STATE
from provisioningserver.utils.shell import ExternalProcessError

ALL_STATUSES = list(NODE_STATUS_CHOICES_DICT)


class FakeNodeAction(NodeAction):
    name = "fake"
    display = "Action label"
    actionable_statuses = ALL_STATUSES
    permission = NodePermission.view
    for_type = [NODE_TYPE.MACHINE]
    action_type = NODE_ACTION_TYPE.MISC

    fake_description = factory.make_name("desc")

    def get_node_action_audit_description(self):
        return self.fake_description

    def _execute(self):
        pass


class TestNodeAction(MAASServerTestCase):
    def test_compile_node_actions_returns_available_actions(self):
        class MyAction(FakeNodeAction):
            name = factory.make_string()

        actions = compile_node_actions(
            factory.make_Node(), factory.make_admin(), classes=[MyAction]
        )
        self.assertEqual([MyAction.name], list(actions.keys()))

    def test_compile_node_actions_checks_node_status(self):
        class MyAction(FakeNodeAction):
            actionable_statuses = (NODE_STATUS.READY,)

        node = factory.make_Node(status=NODE_STATUS.NEW)
        actions = compile_node_actions(
            node, factory.make_admin(), classes=[MyAction]
        )
        self.assertEqual({}, actions)

    def test_compile_node_actions_checks_permission(self):
        class MyAction(FakeNodeAction):
            permission = NodePermission.edit

        node = factory.make_Node(
            status=NODE_STATUS.COMMISSIONING, owner=factory.make_User()
        )
        actions = compile_node_actions(
            node, factory.make_User(), classes=[MyAction]
        )
        self.assertEqual({}, actions)

    def test_compile_node_actions_maps_names(self):
        class Action1(FakeNodeAction):
            name = factory.make_string()

        class Action2(FakeNodeAction):
            name = factory.make_string()

        actions = compile_node_actions(
            factory.make_Node(),
            factory.make_admin(),
            classes=[Action1, Action2],
        )
        for name, action in actions.items():
            self.assertEqual(name, action.name)

    def test_compile_node_actions_maintains_order(self):
        names = [factory.make_string() for counter in range(4)]
        classes = [
            type("Action%d" % counter, (FakeNodeAction,), {"name": name})
            for counter, name in enumerate(names)
        ]
        actions = compile_node_actions(
            factory.make_Node(), factory.make_admin(), classes=classes
        )
        self.assertSequenceEqual(names, list(actions.keys()))
        self.assertSequenceEqual(
            names, [action.name for action in list(actions.values())]
        )

    def test_is_permitted_allows_if_user_has_permission(self):
        class MyAction(FakeNodeAction):
            permission = NodePermission.edit

        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        self.assertTrue(MyAction(node, node.owner).is_permitted())

    def test_is_permitted_disallows_if_user_lacks_permission(self):
        class MyAction(FakeNodeAction):
            permission = NodePermission.edit

        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        self.assertFalse(MyAction(node, factory.make_User()).is_permitted())

    def test_is_permitted_uses_node_permission(self):
        class MyAction(FakeNodeAction):
            permission = NodePermission.view
            node_permission = NodePermission.edit

        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User()
        )
        self.assertFalse(MyAction(node, factory.make_User()).is_permitted())

    def test_is_permitted_doest_use_node_permission_if_device(self):
        class MyAction(FakeNodeAction):
            permission = NodePermission.view
            node_permission = NodePermission.edit

        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            owner=factory.make_User(),
            node_type=NODE_TYPE.DEVICE,
        )
        self.assertTrue(MyAction(node, factory.make_User()).is_permitted())

    def test_node_only_is_not_actionable_if_node_isnt_node_type(self):
        status = NODE_STATUS.NEW
        owner = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = owner
        node = factory.make_Node(
            owner=owner, status=status, node_type=NODE_TYPE.DEVICE
        )
        action = FakeNodeAction(node, owner, request)
        action.node_only = True
        self.assertFalse(action.is_actionable())

    def test_node_only_is_actionable_if_node_type_is_node(self):
        status = NODE_STATUS.NEW
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner, status=status, node_type=NODE_TYPE.MACHINE
        )
        action = FakeNodeAction(node, owner)
        action.node_only = True
        self.assertTrue(action.is_actionable())

    def test_is_actionable_checks_node_status_in_actionable_status(self):
        class MyAction(FakeNodeAction):
            actionable_statuses = [NODE_STATUS.ALLOCATED]

        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        self.assertFalse(MyAction(node, factory.make_User()).is_actionable())

    def test_is_actionable_checks_permission(self):
        class MyAction(FakeNodeAction):
            machine_permission = NodePermission.admin

        node = factory.make_Node()
        self.assertFalse(MyAction(node, factory.make_User()).is_actionable())

    def test_is_actionable_false_if_locked(self):
        class MyAction(FakeNodeAction):
            pass

        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, locked=True)
        self.assertFalse(MyAction(node, factory.make_User()).is_actionable())

    def test_is_actionable_true_if_allowed_when_locked(self):
        class MyAction(FakeNodeAction):
            allowed_when_locked = True

        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, locked=True)
        self.assertTrue(MyAction(node, factory.make_User()).is_actionable())

    def test_is_actionable_no_requires_networking_by_default(self):
        node = factory.make_Node(status=NODE_STATUS.NEW)
        self.assertTrue(
            FakeNodeAction(node, factory.make_User()).is_actionable()
        )

    def test_is_actionable_requires_networking(self):
        class MyAction(FakeNodeAction):
            requires_networking = True

        node = factory.make_Node(status=NODE_STATUS.NEW)
        self.assertFalse(MyAction(node, factory.make_User()).is_actionable())

    def test_delete_action_last_for_node(self):
        node = factory.make_Node()
        actions = compile_node_actions(
            node, factory.make_admin(), classes=ACTION_CLASSES
        )
        self.assertEqual("delete", list(actions)[-1])

    def test_delete_action_last_for_controller(self):
        controller = factory.make_RackController()
        actions = compile_node_actions(
            controller, factory.make_admin(), classes=ACTION_CLASSES
        )
        self.assertEqual("delete", list(actions)[-1])


class TestDeleteAction(MAASServerTestCase):
    def test_users_cannot_delete_controller(self):
        controller = factory.make_RackController()
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        action = Delete(controller, user, request)
        self.assertFalse(action.is_permitted())

    def test_admins_can_delete_controller(self):
        controller = factory.make_RackController()
        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin
        action = Delete(controller, admin, request)
        self.assertTrue(action.is_permitted())

    def test_deletes_node(self):
        node = factory.make_Node()
        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin
        action = Delete(node, admin, request)
        action.execute()
        self.assertIsNone(reload_object(node))
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description,
            "Deleted the '%s' '%s'."
            % (NODE_TYPE_CHOICES_DICT[node.node_type].lower(), node.hostname),
        )

    def test_deletes_when_primary_rack_on_vlan(self):
        # Regression test for LP:1793478.
        rack = factory.make_RackController()
        nic = factory.make_Interface(node=rack)
        vlan = nic.vlan
        vlan.primary_rack = rack
        vlan.dhcp_on = True

        with post_commit_hooks:
            vlan.save()

        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin

        with post_commit_hooks:
            action = Delete(rack, admin, request)
            action.execute()

        self.assertIsNone(reload_object(rack))


class TestCommissionAction(MAASServerTestCase):
    scenarios = (
        ("NEW", {"status": NODE_STATUS.NEW}),
        ("FAILED_COMMISSIONING", {"status": NODE_STATUS.FAILED_COMMISSIONING}),
        ("READY", {"status": NODE_STATUS.READY}),
    )

    def setUp(self):
        super().setUp()
        load_builtin_scripts()

    def test_is_actionable_doesnt_require_interface_if_ipmi(self):
        node = factory.make_Node(status=self.status, power_type="ipmi")
        self.assertTrue(Commission(node, factory.make_admin()).is_actionable())

    def test_Commission_starts_commissioning_if_already_on(self):
        node = factory.make_Node(
            interface=True,
            status=self.status,
            power_type="manual",
            power_state=POWER_STATE.ON,
        )
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin
        action = Commission(node, admin, request)
        with post_commit_hooks:
            action.execute()
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)
        node_start.assert_called_once_with(
            admin, ANY, ANY, allow_power_cycle=True, config=ANY
        )

    def test_Commission_starts_commissioning(self):
        node = factory.make_Node(
            interface=True,
            status=self.status,
            power_type="manual",
            power_state=POWER_STATE.OFF,
        )
        testing_scripts = [
            factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
            for _ in range(3)
        ]
        script_input = {
            "smartctl-validate": {"storage": "sda"},
            "badblocks": {"storage": "sdb"},
        }
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin
        action = Commission(node, admin, request)
        with post_commit_hooks:
            action.execute(
                testing_scripts=testing_scripts, script_input=script_input
            )
        script_sets = ScriptSet.objects.all().order_by("id")
        node = reload_object(node)
        self.assertEqual(2, len(script_sets))
        self.assertEqual(
            node.current_commissioning_script_set_id, script_sets[0].id
        )
        self.assertEqual(node.current_testing_script_set_id, script_sets[1].id)
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)
        node_start.assert_called_once_with(
            admin, ANY, ANY, allow_power_cycle=True, config=ANY
        )

    def test_Commission_logs_audit_event(self):
        node = factory.make_Node(
            interface=True,
            status=self.status,
            power_type="manual",
            power_state=POWER_STATE.OFF,
        )
        node_start = self.patch(node, "_start")
        node_start.side_effect = lambda *args, **kwargs: post_commit()
        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin
        action = Commission(node, admin, request)
        with post_commit_hooks:
            action.execute()
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description,
            "Started commissioning on '%s'." % node.hostname,
        )


class TestTest(MAASServerTestCase):
    def test_starts_testing(self):
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
        enable_ssh = factory.pick_bool()
        self.patch(node, "_start").return_value = None
        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin
        action = Test(node, admin, request)
        with post_commit_hooks:
            action.execute(
                enable_ssh=enable_ssh, testing_scripts=[script.name]
            )
        node = reload_object(node)
        self.assertEqual(NODE_STATUS.TESTING, node.status)
        self.assertEqual(enable_ssh, node.enable_ssh)
        self.assertEqual(
            script.name,
            node.current_testing_script_set.scriptresult_set.first().name,
        )
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, "Started testing on '%s'." % node.hostname
        )


class TestAbortAction(MAASTransactionServerTestCase):
    def test_Abort_aborts_disk_erasing(self):
        self.useFixture(SignalsDisabled("power"))
        with transaction.atomic():
            owner = factory.make_User()
            node = factory.make_Node(
                status=NODE_STATUS.DISK_ERASING, owner=owner
            )
            request = factory.make_fake_request("/")
            request.user = owner

        node_stop = self.patch_autospec(node, "_stop")
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()

        with post_commit_hooks:
            with transaction.atomic():
                Abort(node, owner, request).execute()
                audit_event = Event.objects.get(type__level=AUDIT)
                self.assertEqual(
                    audit_event.description,
                    "Aborted '%s' on '%s'."
                    % (
                        NODE_STATUS_CHOICES_DICT[node.status].lower(),
                        node.hostname,
                    ),
                )

        with transaction.atomic():
            node = reload_object(node)
            self.assertEqual(NODE_STATUS.FAILED_DISK_ERASING, node.status)

        node_stop.assert_called_once_with(owner)

    def test_Abort_aborts_commissioning(self):
        """Makes sure a COMMISSIONING node is returned to NEW status after an
        abort.
        """
        with transaction.atomic():
            node = factory.make_Node(
                interface=True,
                status=NODE_STATUS.COMMISSIONING,
                power_type="virsh",
            )
            admin = factory.make_admin()
            request = factory.make_fake_request("/")
            request.user = admin

        node_stop = self.patch_autospec(node, "_stop")
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()

        with post_commit_hooks:
            with transaction.atomic():
                Abort(node, admin, request).execute()
                audit_event = Event.objects.get(type__level=AUDIT)
                self.assertEqual(
                    audit_event.description,
                    "Aborted '%s' on '%s'."
                    % (
                        NODE_STATUS_CHOICES_DICT[node.status].lower(),
                        node.hostname,
                    ),
                )

        with transaction.atomic():
            node = reload_object(node)
            self.assertEqual(NODE_STATUS.NEW, node.status)

        node_stop.assert_called_once_with(admin)

    def test_Abort_aborts_deployment(self):
        """Makes sure a DEPLOYING node is returned to ALLOCATED status after an
        abort.
        """
        with transaction.atomic():
            node = factory.make_Node(
                interface=True,
                status=NODE_STATUS.DEPLOYING,
                power_type="virsh",
            )
            admin = factory.make_admin()
            request = factory.make_fake_request("/")
            request.user = admin

        node_stop = self.patch_autospec(node, "_stop")
        temporal_stop = self.patch(node_module, "stop_workflow")
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()

        with post_commit_hooks:
            with transaction.atomic():
                Abort(node, admin, request).execute()
                audit_event = Event.objects.get(type__level=AUDIT)
                self.assertEqual(
                    audit_event.description,
                    "Aborted '%s' on '%s'."
                    % (
                        NODE_STATUS_CHOICES_DICT[node.status].lower(),
                        node.hostname,
                    ),
                )

        with transaction.atomic():
            node = reload_object(node)
            self.assertEqual(NODE_STATUS.ALLOCATED, node.status)

        node_stop.assert_called_once_with(admin)
        temporal_stop.assert_called_once_with(f"deploy:{node.system_id}")

    def test_Abort_aborts_testing(self):
        """Makes sure a TESTING node is returned to previous status after an
        abort.
        """
        status = random.choice(list(NODE_TESTING_RESET_READY_TRANSITIONS))
        with transaction.atomic():
            node = factory.make_Node(
                interface=True,
                previous_status=status,
                status=NODE_STATUS.TESTING,
                power_type="virsh",
            )
            admin = factory.make_admin()
            request = factory.make_fake_request("/")
            request.user = admin

        node_stop = self.patch_autospec(node, "_stop")
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()

        with post_commit_hooks:
            with transaction.atomic():
                Abort(node, admin, request).execute()
                audit_event = Event.objects.get(type__level=AUDIT)
                self.assertEqual(
                    audit_event.description,
                    "Aborted '%s' on '%s'."
                    % (
                        NODE_STATUS_CHOICES_DICT[node.status].lower(),
                        node.hostname,
                    ),
                )

        # Allow abortion of auto testing into ready state.
        if status == NODE_STATUS.COMMISSIONING:
            status = NODE_STATUS.READY

        with transaction.atomic():
            node = reload_object(node)
            self.assertEqual(status, node.status)

        node_stop.assert_called_once_with(admin)


class TestAcquireNodeAction(MAASServerTestCase):
    def test_Acquire_acquires_node(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.READY,
            power_type="manual",
            with_boot_disk=True,
        )
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        Acquire(node, user, request).execute()
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)
        self.assertEqual(user, node.owner)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, "Acquired '%s'." % node.hostname
        )

    def test_Acquire_uses_node_acquire_lock(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.READY,
            power_type="manual",
            with_boot_disk=True,
        )
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node_acquire = self.patch(locks, "node_acquire")
        Acquire(node, user, request).execute()
        node_acquire.__enter__.assert_called_once_with()
        node_acquire.__exit__.assert_called_once_with(None, None, None)


class TestDeployAction(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        factory.make_RegionController()

    def test_Deploy_is_actionable_if_user_doesnt_have_ssh_keys(self):
        owner = factory.make_User()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=owner,
        )
        self.assertTrue(Deploy(node, owner).is_actionable())

    def test_Deploy_is_actionable_if_user_has_ssh_keys(self):
        owner = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = owner
        factory.make_SSHKey(owner)
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=owner,
        )
        self.assertTrue(Deploy(node, owner, request).is_actionable())

    def test_Deploy_starts_node(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node_action_module, "get_curtin_config")
        mock_node_start = self.patch(node, "start")
        osystem, releases = make_usable_osystem(self)
        os_name = osystem
        release_name = releases[0]
        Config.objects.set_config("default_osystem", os_name)
        Config.objects.set_config("default_distro_series", release_name)
        Deploy(node, user, request).execute()
        mock_node_start.assert_called_once_with(
            user,
            user_data=None,
            install_kvm=False,
            register_vmhost=False,
            enable_hw_sync=False,
        )
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, "Started deploying '%s'." % node.hostname
        )

    def test_Deploy_passes_user_data(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node_action_module, "get_curtin_config")
        mock_node_start = self.patch(node, "start")
        osystem, releases = make_usable_osystem(self)
        os_name = osystem
        release_name = releases[0]
        Config.objects.set_config("default_osystem", os_name)
        Config.objects.set_config("default_distro_series", release_name)
        extra = {"user_data": "foo: bar"}
        expected = b"foo: bar"
        Deploy(node, user, request).execute(**extra)
        mock_node_start.assert_called_once_with(
            user,
            user_data=expected,
            install_kvm=False,
            register_vmhost=False,
            enable_hw_sync=False,
        )

    def test_Deploy_raises_NodeActionError_for_no_curtin_config(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        mock_get_curtin_config = self.patch(
            node_action_module, "get_curtin_config"
        )
        mock_get_curtin_config.side_effect = NodeActionError("error")
        osystem, releases = make_usable_osystem(self)
        os_name = osystem
        release_name = releases[0]
        Config.objects.set_config("default_osystem", os_name)
        Config.objects.set_config("default_distro_series", release_name)
        error = self.assertRaises(
            NodeActionError, Deploy(node, user, request).execute
        )
        self.assertEqual("Failed to retrieve curtin config: error", str(error))

    def test_Deploy_raises_NodeActionError_for_invalid_os(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node, "start")
        os_name = factory.make_name("os")
        release_name = factory.make_name("release")
        extra = {"osystem": os_name, "distro_series": release_name}
        error = self.assertRaises(
            NodeActionError, Deploy(node, user, request).execute, **extra
        )
        self.assertEqual(
            f"{os_name} is not a supported operating system.",
            str(error),
        )

    def test_Deploy_raises_NodeActionError_invalid_ephemeral_conditions(self):
        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=admin,
        )
        osystem, releases = make_usable_osystem(self)
        os_name = osystem
        release_name = releases[0]

        extra = {
            "osystem": os_name,
            "distro_series": release_name,
            "install_kvm": True,
            "ephemeral_deploy": True,
        }
        with pytest.raises(NodeActionError) as exception:
            Deploy(node, admin, request).execute(**extra)
        assert (
            str(exception.value)
            == "A machine can not be a VM host if it is deployed to memory."
        )

        extra = {
            "osystem": os_name,
            "distro_series": release_name,
            "register_vmhost": True,
            "ephemeral_deploy": True,
        }
        with pytest.raises(NodeActionError) as exception:
            Deploy(node, admin, request).execute(**extra)
        assert (
            str(exception.value)
            == "A machine can not be a VM host if it is deployed to memory."
        )

    def test_Deploy_sets_osystem_and_series_and_ephemeral_deploy(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")

        osystem, releases = make_usable_osystem(
            self, osystem_name="ubuntu", releases=["noble"]
        )
        os_name = osystem
        release_name = releases[0]
        extra = {
            "osystem": os_name,
            "distro_series": release_name,
            "ephemeral_deploy": True,
        }
        Deploy(node, user, request).execute(**extra)
        assert node.osystem == os_name
        assert node.distro_series == release_name
        assert node.ephemeral_deploy is True

    def test_Deploy_diskless_without_ephemeral_raises_an_exception(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
            with_boot_disk=False,
        )
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")
        osystem, releases = make_usable_osystem(
            self, osystem_name="ubuntu", releases=["focal"]
        )
        os_name = osystem
        release_name = releases[0]
        extra = {"osystem": os_name, "distro_series": release_name}
        with pytest.raises(NodeActionError) as exception:
            Deploy(node, user, request).execute(**extra)
        assert (
            str(exception.value)
            == "Can’t deploy to disk in a diskless machine. Deploy to memory must be used instead."
        )

    def test_Deploy_sets_osystem_and_series_and_ephemeral_deploy_to_default(
        self,
    ):
        # Regression test for LP:1822173
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")
        osystem, releases = make_usable_osystem(
            self, osystem_name="ubuntu", releases=["noble"]
        )
        os_name = osystem
        release_name = releases[0]
        Config.objects.set_config("default_osystem", os_name)
        Config.objects.set_config("default_distro_series", release_name)
        Deploy(node, user, request).execute()
        assert node.osystem == os_name
        assert node.distro_series == release_name
        assert node.ephemeral_deploy is False

    def test_Deploy_passes_install_kvm_if_specified(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node_action_module, "get_curtin_config")
        mock_node_start = self.patch(node, "start")
        osystem, releases = make_usable_osystem(self)
        os_name = osystem
        release_name = releases[0]
        extra = {
            "osystem": os_name,
            "distro_series": release_name,
            "install_kvm": True,
        }
        Deploy(node, user, request).execute(**extra)
        self.assertEqual(node.osystem, os_name)
        self.assertEqual(node.distro_series, release_name)
        mock_node_start.assert_called_once_with(
            user,
            user_data=None,
            install_kvm=True,
            register_vmhost=False,
            enable_hw_sync=False,
        )

    def test_Deploy_raises_NodeActionError_on_install_kvm_if_os_missing(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node, "start")
        extra = {"install_kvm": True}
        self.assertRaises(
            NodeActionError, Deploy(node, user, request).execute, **extra
        )

    def test_Deploy_raises_NodeActionError_if_non_admin_install_kvm(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node, "start")
        extra = {"install_kvm": True}
        self.assertRaises(
            NodeActionError, Deploy(node, user, request).execute, **extra
        )

    def test_Deploy_raises_NodeActionError_on_register_vmhost_if_os_missing(
        self,
    ):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node, "start")
        extra = {"register_vmhost": True}
        self.assertRaises(
            NodeActionError, Deploy(node, user, request).execute, **extra
        )

    def test_Deploy_raises_NodeActionError_if_non_admin_register_vmhost(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node, "start")
        extra = {"register_vmhost": True}
        self.assertRaises(
            NodeActionError, Deploy(node, user, request).execute, **extra
        )

    def test_Deploy_sets_osystem_and_series_strips_license_key_token(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")
        osystem, releases = make_usable_osystem(self)
        os_name = osystem
        release_name = releases[0]
        extra = {"osystem": os_name, "distro_series": release_name + "*"}
        Deploy(node, user, request).execute(**extra)
        self.assertEqual(node.osystem, os_name)
        self.assertEqual(node.distro_series, release_name)

    def test_Deploy_allocates_node_if_node_not_already_allocated(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")
        osystem, releases = make_usable_osystem(self)
        os_name = osystem
        release_name = releases[0]
        Config.objects.set_config("default_osystem", os_name)
        Config.objects.set_config("default_distro_series", release_name)
        action = Deploy(node, user, request)
        action.execute()

        self.assertEqual(user, node.owner)
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)

    def test_Deploy_raises_an_error_when_enable_hw_sync_is_True_for_non_linux(
        self,
    ):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")
        osystem, releases = make_usable_osystem(self, osystem_name="windows")
        os_name = osystem
        release_name = releases[0]
        Config.objects.set_config("default_osystem", os_name)
        Config.objects.set_config("default_distro_series", release_name)
        extra = {"enable_hw_sync": True}
        action = Deploy(node, user, request)
        self.assertRaises(NodeActionError, action.execute, **extra)

    def test_Deploy_enable_kernel_crash_dump_default(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        Config.objects.set_config(name="enable_kernel_crash_dump", value=True)
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
            cpu_count=4,
            memory=6 * 1024,
            architecture=make_usable_architecture(self, arch_name="amd64"),
        )
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")

        osystem, releases = make_usable_osystem(
            self, osystem_name="ubuntu", releases=["jammy"]
        )
        os_name = osystem
        extra = {
            "osystem": os_name,
            "ephemeral_deploy": True,
        }
        Deploy(node, user, request).execute(**extra)
        assert node.osystem == os_name
        assert node.enable_kernel_crash_dump is True

    def test_Deploy_set_enable_kernel_crash_dump(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
            cpu_count=4,
            memory=6 * 1024,
            architecture=make_usable_architecture(self, arch_name="amd64"),
        )
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")

        osystem, releases = make_usable_osystem(
            self, osystem_name="ubuntu", releases=["jammy"]
        )
        os_name = osystem
        extra = {"osystem": os_name, "enable_kernel_crash_dump": True}
        Deploy(node, user, request).execute(**extra)
        assert node.osystem == os_name
        assert node.enable_kernel_crash_dump is True

    def test_Deploy_set_enable_kernel_crash_dump_overrides_default(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        Config.objects.set_config(name="enable_kernel_crash_dump", value=True)
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
            cpu_count=4,
            memory=6 * 1024,
            architecture=make_usable_architecture(self, arch_name="amd64"),
        )
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")

        osystem, releases = make_usable_osystem(
            self, osystem_name="ubuntu", releases=["jammy"]
        )
        os_name = osystem
        extra = {"osystem": os_name, "enable_kernel_crash_dump": False}
        Deploy(node, user, request).execute(**extra)
        assert node.osystem == os_name
        assert node.enable_kernel_crash_dump is False

    def test_Deploy_set_enable_kernel_crash_dump_requirements_not_satisfied(
        self,
    ):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
            cpu_count=3,  # not enough cpu
            memory=6 * 1024,
            architecture=make_usable_architecture(self, arch_name="amd64"),
        )
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")

        osystem, releases = make_usable_osystem(
            self, osystem_name="ubuntu", releases=["jammy"]
        )
        os_name = osystem
        extra = {"osystem": os_name, "enable_kernel_crash_dump": True}
        Deploy(node, user, request).execute(**extra)
        assert node.osystem == os_name
        assert node.enable_kernel_crash_dump is False
        assert Notification.objects.filter(
            ident=f"kernel_crash_{node.system_id}"
        ).exists()

    def test_Deploy_set_enable_kernel_crash_dump_arch_invalid(
        self,
    ):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
            cpu_count=4,
            memory=6 * 1024,
            architecture="armhf/generic",
        )
        self.patch(node_action_module, "get_curtin_config")
        self.patch(node, "start")

        osystem, releases = make_usable_osystem(
            self, osystem_name="ubuntu", releases=["jammy"]
        )
        os_name = osystem
        extra = {"osystem": os_name, "enable_kernel_crash_dump": True}
        Deploy(node, user, request).execute(**extra)
        assert node.osystem == os_name
        assert node.enable_kernel_crash_dump is False
        assert Notification.objects.filter(
            ident=f"kernel_crash_{node.system_id}"
        ).exists()


class TestDeployActionTransactional(MAASTransactionServerTestCase):
    """The following TestDeployAction tests require
    MAASTransactionServerTestCase, and thus, have been separated
    from the TestDeployAction above.
    """

    def setUp(self):
        super().setUp()
        factory.make_RegionController()
        self.patch(node_module.Node, "_temporal_deploy")

    def test_Deploy_returns_error_when_no_more_static_IPs(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        network = IPNetwork("10.0.0.0/30")
        subnet = factory.make_Subnet(cidr=str(network.cidr))
        rack_controller = factory.make_RackController()
        subnet.vlan.dhcp_on = True
        subnet.vlan.primary_rack = rack_controller

        with post_commit_hooks:
            subnet.vlan.save()

        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            power_type="virsh",
            owner=user,
            power_state=POWER_STATE.OFF,
            bmc_connected_to=rack_controller,
        )
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node, vlan=subnet.vlan
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            ip="",
            subnet=subnet,
            interface=interface,
        )
        client = Mock()
        client.ident = rack_controller.system_id
        self.patch(power_module, "getAllClients").return_value = [client]

        make_usable_osystem(self)

        # Pre-claim the only addresses.
        with transaction.atomic():
            with post_commit_hooks:
                StaticIPAddress.objects.allocate_new(
                    subnet, requested_address="10.0.0.1"
                )
                StaticIPAddress.objects.allocate_new(
                    subnet, requested_address="10.0.0.2"
                )
                StaticIPAddress.objects.allocate_new(
                    subnet, requested_address="10.0.0.3"
                )

        e = self.assertRaises(
            NodeActionError, Deploy(node, user, request).execute
        )
        self.assertEqual(
            str(e),
            f"{node.hostname}: Failed to start, static IP addresses are exhausted.",
        )
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)


class TestSetZoneAction(MAASServerTestCase):
    def test_SetZone_sets_zone(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        zone1 = factory.make_Zone()
        zone2 = factory.make_Zone()
        node = factory.make_Node(status=NODE_STATUS.NEW, zone=zone1)
        action = SetZone(node, user, request)
        action.execute(zone_id=zone2.id)
        self.assertEqual(node.zone.id, zone2.id)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description,
            f"Set the zone to '{node.zone.name}' on '{node.hostname}'.",
        )

    def test_is_acionable_true_for_owned_device(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        device = factory.make_Device(owner=user)
        action = SetZone(device, user, request)
        self.assertTrue(action.is_actionable())

    def test_is_acionable_false_not_owner(self):
        device = factory.make_Device(owner=factory.make_User())
        action = SetZone(device, factory.make_User())
        self.assertFalse(action.is_actionable())


class TestSetPoolAction(MAASServerTestCase):
    def test_SetPool_sets_pool(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        node = factory.make_Node(status=NODE_STATUS.NEW, pool=pool1)
        action = SetPool(node, user, request)
        action.execute(pool_id=pool2.id)
        self.assertEqual(reload_object(node).pool.id, pool2.id)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description,
            "Set the resource pool to '%s' on '%s'."
            % (node.pool.name, node.hostname),
        )


class TestAddTagAction(MAASServerTestCase):
    def test_AddTag_adds_tag(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        tags = [factory.make_Tag(definition="") for _ in range(3)]
        node = factory.make_Node(status=NODE_STATUS.NEW)
        action = AddTag(node, user, request)
        action.execute(tags=[tag.id for tag in tags])
        self.assertCountEqual(tags, reload_object(node).tags.all())

    def test_requires_admin_permission(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node()
        self.assertFalse(AddTag(node, user, request).is_permitted())


class TestRemoveTagAction(MAASServerTestCase):
    def test_RemoveTag_removes_tag(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        tags = [factory.make_Tag(definition="") for _ in range(3)]
        node = factory.make_Node(status=NODE_STATUS.NEW)
        node.tags.set(tags)
        action = RemoveTag(node, user, request)
        action.execute(tags=[tag.id for tag in tags])
        self.assertFalse(reload_object(node).tags.exists())

    def test_requires_admin_permission(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node()
        self.assertFalse(RemoveTag(node, user, request).is_permitted())


class TestPowerOnAction(MAASServerTestCase):
    def test_PowerOn_starts_node(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.ALLOCATED,
            power_type="manual",
            owner=user,
        )
        node_start = self.patch(node, "start")
        PowerOn(node, user, request).execute()
        node_start.assert_called_once_with(user)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, "Powered on '%s'." % node.hostname
        )

    def test_PowerOn_requires_edit_permission(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=factory.make_User())
        self.assertFalse(user.has_perm(NodePermission.edit, node))
        self.assertFalse(PowerOn(node, user, request).is_permitted())

    def test_PowerOn_is_actionable_if_node_doesnt_have_an_owner(self):
        owner = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = owner
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DEPLOYED, power_type="manual"
        )
        self.assertTrue(PowerOn(node, owner, request).is_actionable())

    def test_PowerOn_is_actionable_if_node_does_have_an_owner(self):
        owner = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = owner
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYED,
            power_type="manual",
            owner=owner,
        )
        self.assertTrue(PowerOn(node, owner, request).is_actionable())


class TestPowerOffAction(MAASServerTestCase):
    def test_stops_deployed_node(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        params = dict(
            power_address=factory.make_ipv4_address(),
            power_user=factory.make_string(),
            power_pass=factory.make_string(),
        )
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYED,
            power_type="ipmi",
            owner=user,
            power_parameters=params,
        )
        node_stop = self.patch_autospec(node, "stop")

        PowerOff(node, user, request).execute()

        node_stop.assert_called_once_with(user, stop_mode=None)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, f"Powered off '{node.hostname}'."
        )

    def test_can_stop_with_soft_stop_mode(self):
        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin
        params = dict(
            power_address=factory.make_ipv4_address(),
            power_user=factory.make_string(),
            power_pass=factory.make_string(),
        )
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.READY,
            power_type="ipmi",
            power_parameters=params,
        )
        node_stop = self.patch_autospec(node, "stop")

        PowerOff(node, admin, request).execute(stop_mode="soft")

        node_stop.assert_called_once_with(admin, stop_mode="soft")

    def test_stops_Ready_node(self):
        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin
        params = dict(
            power_address=factory.make_ipv4_address(),
            power_user=factory.make_string(),
            power_pass=factory.make_string(),
        )
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.READY,
            power_type="ipmi",
            power_parameters=params,
        )
        node_stop = self.patch_autospec(node, "stop")

        PowerOff(node, admin, request).execute()

        node_stop.assert_called_once_with(admin, stop_mode=None)

    def test_actionable_for_non_monitored_states(self):
        all_statuses = NON_MONITORED_STATUSES
        results = {}
        for status in all_statuses:
            node = factory.make_Node(
                status=status,
                power_type="ipmi",
                power_parameters={"power_address": factory.make_ip_address()},
                power_state=POWER_STATE.ON,
            )
            actions = compile_node_actions(
                node, factory.make_admin(), classes=[PowerOff]
            )
            results[status] = list(actions.keys())
        expected_results = {status: [PowerOff.name] for status in all_statuses}
        self.assertEqual(
            expected_results,
            results,
            "Nodes with certain statuses could not be powered off.",
        )

    def test_non_actionable_for_monitored_states(self):
        all_statuses = MONITORED_STATUSES
        results = {}
        for status in all_statuses:
            node = factory.make_Node(
                status=status,
                power_type="ipmi",
                power_parameters={"power_address": factory.make_ip_address()},
                power_state=POWER_STATE.ON,
            )
            actions = compile_node_actions(
                node, factory.make_admin(), classes=[PowerOff]
            )
            results[status] = list(actions.keys())
        expected_results = {status: [] for status in all_statuses}
        self.assertEqual(
            expected_results,
            results,
            "Nodes with certain statuses could be powered off.",
        )

    def test_non_actionable_if_node_already_off(self):
        all_statuses = NON_MONITORED_STATUSES
        results = {}
        for status in all_statuses:
            node = factory.make_Node(
                status=status,
                power_type="ipmi",
                power_parameters={"power_address": factory.make_ip_address()},
                power_state=POWER_STATE.OFF,
            )
            actions = compile_node_actions(
                node, factory.make_admin(), classes=[PowerOff]
            )
            results[status] = list(actions.keys())
        expected_results = {status: [] for status in all_statuses}
        self.assertEqual(
            expected_results,
            results,
            "Nodes already powered off can be powered off.",
        )


class TestLockAction(MAASServerTestCase):
    def test_changes_locked_status_deployed(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED, owner=user)
        action = Lock(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertTrue(reload_object(node).locked)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, "Locked '%s'." % node.hostname
        )

    def test_changes_locked_status_deploying(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(status=NODE_STATUS.DEPLOYING, owner=user)
        action = Lock(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertTrue(reload_object(node).locked)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, "Locked '%s'." % node.hostname
        )

    def test_not_actionable_if_wrong_status(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(status=NODE_STATUS.READY, owner=user)
        action = Lock(node, user, request)
        self.assertFalse(action.is_actionable())

    def test_not_actionable_if_locked(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED, owner=user, locked=True
        )
        action = Lock(node, user, request)
        self.assertFalse(action.is_actionable())

    def test_not_actionable_if_not_machine(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        controller = factory.make_RackController()
        action = Lock(controller, user, request)
        self.assertFalse(action.is_actionable())


class TestUnlockAction(MAASServerTestCase):
    def test_changes_locked_status(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(locked=True, owner=user)
        action = Unlock(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertFalse(reload_object(node).locked)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, "Unlocked '%s'." % node.hostname
        )

    def test_not_actionable_if_not_locked(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=user)
        action = Unlock(node, user, request)
        self.assertFalse(action.is_actionable())

    def test_not_actionable_if_not_machine(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        controller = factory.make_RackController()
        action = Unlock(controller, user, request)
        self.assertFalse(action.is_actionable())


ACTIONABLE_STATUSES = [
    NODE_STATUS.DEPLOYING,
    NODE_STATUS.FAILED_DEPLOYMENT,
    NODE_STATUS.FAILED_DISK_ERASING,
]


class TestReleaseAction(MAASServerTestCase):
    scenarios = [
        (NODE_STATUS_CHOICES_DICT[status], dict(actionable_status=status))
        for status in ACTIONABLE_STATUSES
    ]

    def test_Release_stops_and_releases_node(self):
        self.patch(node_module, "stop_workflow")
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        params = dict(
            power_address=factory.make_ipv4_address(),
            power_user=factory.make_string(),
            power_pass=factory.make_string(),
        )
        node = factory.make_Node(
            interface=True,
            status=self.actionable_status,
            power_type="ipmi",
            power_state=POWER_STATE.ON,
            owner=user,
            power_parameters=params,
        )
        node_stop = self.patch_autospec(node, "_stop")

        with post_commit_hooks:
            Release(node, user, request).execute()

        self.assertEqual(node.status, NODE_STATUS.RELEASING)
        node_stop.assert_called_once_with(user)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, "Started releasing '%s'." % node.hostname
        )

    def test_Release_enters_disk_erasing(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        params = dict(
            power_address=factory.make_ipv4_address(),
            power_user=factory.make_string(),
            power_pass=factory.make_string(),
        )
        node = factory.make_Node(
            interface=True,
            status=self.actionable_status,
            power_type="ipmi",
            power_state=POWER_STATE.OFF,
            owner=user,
            power_parameters=params,
        )
        old_status = node.status
        node_start = self.patch_autospec(node, "_start")
        node_start.return_value = None

        with post_commit_hooks:
            Release(node, user, request).execute(erase=True)

        self.assertEqual(node.status, NODE_STATUS.DISK_ERASING)
        node_start.assert_called_once_with(
            user,
            user_data=ANY,
            old_status=old_status,
            allow_power_cycle=True,
            config=ANY,
        )

    def test_Release_passes_secure_erase_and_quick_erase(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        params = dict(
            power_address=factory.make_ipv4_address(),
            power_user=factory.make_string(),
            power_pass=factory.make_string(),
        )
        node = factory.make_Node(
            interface=True,
            status=self.actionable_status,
            power_type="ipmi",
            power_state=POWER_STATE.OFF,
            owner=user,
            power_parameters=params,
        )
        node_start_releasing = self.patch_autospec(node, "start_releasing")

        with post_commit_hooks:
            Release(node, user, request).execute(
                erase=True, secure_erase=True, quick_erase=True
            )

        node_start_releasing.assert_called_once_with(
            user=user,
            scripts=["wipe-disks"],
            script_input={
                "wipe-disks": {"secure_erase": True, "quick_erase": True}
            },
        )


class TestMarkBrokenAction(MAASServerTestCase):
    def test_changes_status(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=user, status=NODE_STATUS.COMMISSIONING)
        action = MarkBroken(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, "Marked '%s' broken." % node.hostname
        )

    def test_updates_error_description(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=user, status=NODE_STATUS.COMMISSIONING)
        action = MarkBroken(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual("", reload_object(node).error_description)

    def test_user_provided_description(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=user, status=NODE_STATUS.COMMISSIONING)
        action = MarkBroken(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute(message="Provided broken message")
        self.assertEqual(
            "Provided broken message", reload_object(node).error_description
        )

    def test_requires_edit_permission(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=factory.make_User())
        self.assertFalse(MarkBroken(node, user, request).is_permitted())


class TestMarkFixedAction(MAASServerTestCase):
    def make_commissioning_data(self, node, result=0, count=3):
        script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.COMMISSIONING
        )
        node.current_commissioning_script_set = script_set
        node.save()
        if result == 0:
            status = SCRIPT_STATUS.PASSED
        elif result == 1:
            status = SCRIPT_STATUS.FAILED
        elif result == -1:
            status = SCRIPT_STATUS.SKIPPED
        return [
            factory.make_ScriptResult(
                script_set=script_set, exit_status=result, status=status
            )
            for _ in range(count)
        ]

    def test_changes_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, power_state=POWER_STATE.ON
        )
        self.make_commissioning_data(node)
        self.make_commissioning_data(node, result=-1)
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        action = MarkFixed(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, "Marked '%s' fixed." % node.hostname
        )

    def test_raise_NodeActionError_if_on(self):
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, power_state=POWER_STATE.ON
        )
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        action = MarkFixed(node, user, request)
        self.assertTrue(action.is_permitted())
        self.assertRaises(NodeActionError, action.execute)

    def test_raise_NodeActionError_if_no_commissioning_results(self):
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, power_state=POWER_STATE.OFF
        )
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        action = MarkFixed(node, user, request)
        self.assertTrue(action.is_permitted())
        self.assertRaises(NodeActionError, action.execute)

    def test_raise_NodeActionError_if_one_commissioning_result_fails(self):
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, power_state=POWER_STATE.OFF
        )
        self.make_commissioning_data(node)
        self.make_commissioning_data(node, result=1, count=1)
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        action = MarkFixed(node, user, request)
        self.assertTrue(action.is_permitted())
        self.assertRaises(NodeActionError, action.execute)

    def test_raise_NodeActionError_if_multi_commissioning_result_fails(self):
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, power_state=POWER_STATE.OFF
        )
        self.make_commissioning_data(node)
        self.make_commissioning_data(node, result=1)
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        action = MarkFixed(node, user, request)
        self.assertTrue(action.is_permitted())
        self.assertRaises(NodeActionError, action.execute)

    def test_requires_admin_permission(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node()
        self.assertFalse(MarkFixed(node, user, request).is_permitted())

    def test_not_enabled_if_not_broken(self):
        status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=[NODE_STATUS.BROKEN]
        )
        node = factory.make_Node(status=status)
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        actions = compile_node_actions(
            node, factory.make_admin(), classes=[MarkFixed], request=request
        )
        self.assertEqual({}, actions)


class TestOverrideFailedTesting(MAASServerTestCase):
    def create_script_results(self, nodes, count=5):
        script_results = []
        for node in nodes:
            script = factory.make_Script()
            for _ in range(count):
                script_set = factory.make_ScriptSet(
                    result_type=script.script_type, node=node
                )
                factory.make_ScriptResult(script=script, script_set=script_set)

            script_set = factory.make_ScriptSet(
                result_type=script.script_type, node=node
            )
            script_result = factory.make_ScriptResult(
                script=script,
                script_set=script_set,
                status=random.choice(
                    list(SCRIPT_STATUS_FAILED.union({SCRIPT_STATUS.PASSED}))
                ),
            )
            if script.script_type == SCRIPT_TYPE.TESTING and (
                script_result.status in SCRIPT_STATUS_FAILED
            ):
                script_results.append(script_result)
        return script_results

    def test_ignore_tests_sets_status_to_ready(self):
        owner = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = owner
        description = factory.make_name("error-description")
        node = factory.make_Node(
            status=NODE_STATUS.FAILED_TESTING,
            owner=owner,
            error_description=description,
            osystem="",
        )
        failed_scripts = self.create_script_results(nodes=[node])
        action = OverrideFailedTesting(node, owner, request)
        self.assertTrue(action.is_permitted())
        action.execute(suppress_failed_script_results=True)
        node = reload_object(node)
        self.assertEqual(NODE_STATUS.READY, node.status)
        self.assertEqual("", node.osystem)
        self.assertEqual("", node.error_description)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description,
            "Overrode failed testing on '%s'." % node.hostname,
        )
        for script_result in failed_scripts:
            script_result = reload_object(script_result)
            self.assertTrue(script_result.suppressed)

    def test_ignore_tests_sets_status_to_deployed(self):
        owner = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = owner
        osystem = factory.make_name("osystem")
        description = factory.make_name("error-description")
        node = factory.make_Node(
            status=NODE_STATUS.FAILED_TESTING,
            owner=owner,
            error_description=description,
            osystem=osystem,
        )
        action = OverrideFailedTesting(node, owner, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        node = reload_object(node)
        self.assertEqual(NODE_STATUS.DEPLOYED, node.status)
        self.assertEqual(osystem, node.osystem)
        self.assertEqual("", node.error_description)

    def test_requires_admin(self):
        owner = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = owner
        node = factory.make_Node(
            status=NODE_STATUS.FAILED_TESTING, owner=owner
        )
        action = OverrideFailedTesting(node, owner, request)
        self.assertFalse(action.is_permitted())


class TestRescueModeAction(MAASServerTestCase):
    def test_requires_admin_permission(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node()
        self.assertFalse(RescueMode(node, user, request).is_permitted())

    def test_rescue_mode_action_for_ready(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=user, status=NODE_STATUS.READY)
        node_start_rescue_mode = self.patch_autospec(node, "start_rescue_mode")
        action = RescueMode(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        node_start_rescue_mode.assert_called_once_with(user)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description,
            "Started rescue mode on '%s'." % node.hostname,
        )

    def test_rescue_mode_action_for_broken(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=user, status=NODE_STATUS.BROKEN)
        node_start_rescue_mode = self.patch_autospec(node, "start_rescue_mode")
        action = RescueMode(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        node_start_rescue_mode.assert_called_once_with(user)

    def test_rescue_mode_action_for_deployed(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=user, status=NODE_STATUS.DEPLOYED)
        node_start_rescue_mode = self.patch_autospec(node, "start_rescue_mode")
        action = RescueMode(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        node_start_rescue_mode.assert_called_once_with(user)


class TestExitRescueModeAction(MAASServerTestCase):
    def test_requires_admin_permission(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node()
        self.assertFalse(ExitRescueMode(node, user, request).is_permitted())

    def test_exit_rescue_mode_action_for_ready(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=user, status=NODE_STATUS.READY)
        node_stop_rescue_mode = self.patch_autospec(node, "stop_rescue_mode")
        action = ExitRescueMode(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        node_stop_rescue_mode.assert_called_once_with(user)
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description,
            "Exited rescue mode on '%s'." % node.hostname,
        )

    def test_exit_rescue_mode_action_for_broken(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=user, status=NODE_STATUS.BROKEN)
        node_stop_rescue_mode = self.patch_autospec(node, "stop_rescue_mode")
        action = ExitRescueMode(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        node_stop_rescue_mode.assert_called_once_with(user)

    def test_exit_rescue_mode_action_for_deployed(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node(owner=user, status=NODE_STATUS.DEPLOYED)
        node_stop_rescue_mode = self.patch_autospec(node, "stop_rescue_mode")
        action = ExitRescueMode(node, user, request)
        self.assertTrue(action.is_permitted())
        action.execute()
        node_stop_rescue_mode.assert_called_once_with(user)


class TestCloneAction(MAASServerTestCase):
    def test_admin_permission_required(self):
        user = factory.make_User()
        request = factory.make_fake_request("/")
        request.user = user
        node = factory.make_Node()
        self.assertFalse(Clone(node, user, request).is_permitted())

    def test_requires_destinations(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        source = factory.make_Machine()
        action = Clone(source, user, request)
        exception = self.assertRaises(
            NodeActionError, action.execute, storage=True, interfaces=True
        )
        (error,) = exception.args
        self.assertEqual(
            json.loads(error)["destinations"],
            [{"code": "required", "message": "This field is required."}],
        )

    def test_requires_storage_or_interfaces(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        source = factory.make_Machine()
        destination1 = factory.make_Machine(
            status=NODE_STATUS.READY,
            with_boot_disk=False,
        )
        action = Clone(source, user, request)
        exception = self.assertRaises(
            NodeActionError,
            action.execute,
            destinations=[destination1.system_id],
        )
        (error,) = exception.args
        self.assertEqual(
            json.loads(error)["__all__"],
            [
                {
                    "code": "required",
                    "message": "Either storage or interfaces must be true.",
                }
            ],
        )

    def test_clone_action_log(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        source = factory.make_Machine(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=source, size=8 * 1024**3, name="sda"
        )
        factory.make_Interface(node=source, name="eth0")
        destination1 = factory.make_Machine(
            status=NODE_STATUS.READY,
            with_boot_disk=False,
        )
        factory.make_PhysicalBlockDevice(
            node=destination1, size=8 * 1024**3, name="sda"
        )
        factory.make_Interface(node=destination1, name="eth0")
        destination2 = factory.make_Machine(
            status=NODE_STATUS.FAILED_TESTING,
            with_boot_disk=False,
        )
        factory.make_PhysicalBlockDevice(
            node=destination2, size=8 * 1024**3, name="sda"
        )
        factory.make_Interface(node=destination2, name="eth0")

        action = Clone(source, user, request)

        with post_commit_hooks:
            action.execute(
                destinations=[destination1.system_id, destination2.system_id],
                storage=True,
                interfaces=True,
            )
        audit_event = Event.objects.get(type__level=AUDIT)
        self.assertEqual(
            audit_event.description, f"Cloning from '{source.hostname}'."
        )

    def test_clone_errors_include_system_id(self):
        user = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = user
        source = factory.make_Machine(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        factory.make_PhysicalBlockDevice(
            node=source, size=8 * 1024**3, name="sda"
        )
        destination = factory.make_Machine(
            status=NODE_STATUS.READY, with_boot_disk=False
        )
        factory.make_PhysicalBlockDevice(
            node=destination, size=4 * 1024**3, name="sda"
        )
        action = Clone(source, user, request)
        exception = self.assertRaises(
            NodeActionError,
            action.execute,
            destinations=[destination.system_id],
            storage=True,
        )
        (error,) = exception.args
        self.assertEqual(
            json.loads(error)["destinations"],
            [
                {
                    "code": "storage",
                    "message": f"{destination} is invalid: destination boot disk(sda) is smaller than source boot disk(sda)",
                    "system_id": destination.system_id,
                }
            ],
        )


class TestActionsErrorHandling(MAASServerTestCase):
    """Tests for error handling in actions.

    This covers RPC exceptions and `ExternalProcessError`s.
    """

    exceptions = RPC_EXCEPTIONS + (ExternalProcessError,)
    scenarios = [
        (exception_class.__name__, {"exception_class": exception_class})
        for exception_class in exceptions
    ]

    def make_exception(self):
        if self.exception_class is ExternalProcessError:
            exception = self.exception_class(
                1, ["cmd"], factory.make_name("exception")
            )
        else:
            exception = self.exception_class(factory.make_name("exception"))
        return exception

    def patch_rpc_methods(self, node):
        exception = self.make_exception()
        self.patch(node, "_start").side_effect = exception
        self.patch(node, "_stop").side_effect = exception

    def make_action(
        self,
        action_class,
        node_status,
        power_state=None,
        node_type=NODE_TYPE.MACHINE,
    ):
        node = factory.make_Node(
            interface=True,
            status=node_status,
            power_type="manual",
            power_state=power_state,
            node_type=node_type,
        )
        admin = factory.make_admin()
        request = factory.make_fake_request("/")
        request.user = admin
        return action_class(node.as_self(), admin, request)

    def test_Commission_handles_rpc_errors(self):
        self.addCleanup(signals.power.signals.enable)
        signals.power.signals.disable()

        action = self.make_action(
            Commission, NODE_STATUS.READY, POWER_STATE.OFF
        )
        self.patch_rpc_methods(action.node)
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(action.node._start.side_effect),
            str(exception),
        )

    def test_Abort_handles_rpc_errors(self):
        action = self.make_action(Abort, NODE_STATUS.DISK_ERASING)
        self.patch_rpc_methods(action.node)
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(action.node._stop.side_effect),
            str(exception),
        )

    def test_PowerOn_handles_rpc_errors(self):
        action = self.make_action(PowerOn, NODE_STATUS.READY)
        self.patch_rpc_methods(action.node)
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(action.node._start.side_effect),
            str(exception),
        )

    def test_PowerOff_handles_rpc_errors(self):
        action = self.make_action(PowerOff, NODE_STATUS.DEPLOYED)
        self.patch_rpc_methods(action.node)
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(action.node._stop.side_effect),
            str(exception),
        )

    def test_Release_handles_rpc_errors(self):
        action = self.make_action(
            Release, NODE_STATUS.ALLOCATED, power_state=POWER_STATE.ON
        )
        self.patch_rpc_methods(action.node)
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(action.node._stop.side_effect),
            str(exception),
        )

    def test_RescueMode_handles_rpc_errors_for_entering_rescue_mode(self):
        action = self.make_action(
            RescueMode,
            random.choice(
                [
                    NODE_STATUS.READY,
                    NODE_STATUS.BROKEN,
                    NODE_STATUS.DEPLOYED,
                    NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
                ]
            ),
        )
        self.patch(
            action.node, "start_rescue_mode"
        ).side_effect = self.make_exception()
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(
                action.node.start_rescue_mode.side_effect
            ),
            str(exception),
        )

    def test_ExitRescueMode_handles_rpc_errors_for_exiting_rescue_mode(self):
        action = self.make_action(
            ExitRescueMode,
            random.choice(
                [
                    NODE_STATUS.RESCUE_MODE,
                    NODE_STATUS.ENTERING_RESCUE_MODE,
                    NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
                    NODE_STATUS.FAILED_EXITING_RESCUE_MODE,
                ]
            ),
        )
        self.patch(
            action.node, "stop_rescue_mode"
        ).side_effect = self.make_exception()
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(
                action.node.stop_rescue_mode.side_effect
            ),
            str(exception),
        )
