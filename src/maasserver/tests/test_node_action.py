# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for node actions."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []

from django.db import transaction
from maasserver import locks
from maasserver.clusterrpc.utils import get_error_message_for_exception
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    POWER_STATE,
)
from maasserver.exceptions import NodeActionError
from maasserver.models import StaticIPAddress
from maasserver.node_action import (
    Abort,
    Acquire,
    Commission,
    compile_node_actions,
    Delete,
    Deploy,
    MarkBroken,
    MarkFixed,
    NodeAction,
    PowerOff,
    PowerOn,
    Release,
    RPC_EXCEPTIONS,
    SetZone,
)
from maasserver.node_status import (
    MONITORED_STATUSES,
    NON_MONITORED_STATUSES,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.osystems import make_osystem_with_releases
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import (
    post_commit,
    post_commit_hooks,
)
from maastesting.matchers import MockCalledOnceWith
from mock import ANY
from provisioningserver.rpc.exceptions import MultipleFailures
from provisioningserver.utils.shell import ExternalProcessError
from testtools.matchers import Equals
from twisted.python.failure import Failure


ALL_STATUSES = NODE_STATUS_CHOICES_DICT.keys()


class FakeNodeAction(NodeAction):
    name = "fake"
    display = "Action label"
    actionable_statuses = ALL_STATUSES
    permission = NODE_PERMISSION.VIEW
    installable_only = False

    # For testing: an inhibition for inhibit() to return.
    fake_inhibition = None

    def inhibit(self):
        return self.fake_inhibition

    def execute(self):
        pass


class TestNodeAction(MAASServerTestCase):

    def test_compile_node_actions_returns_available_actions(self):

        class MyAction(FakeNodeAction):
            name = factory.make_string()

        actions = compile_node_actions(
            factory.make_Node(), factory.make_admin(), classes=[MyAction])
        self.assertEqual([MyAction.name], actions.keys())

    def test_compile_node_actions_checks_node_status(self):

        class MyAction(FakeNodeAction):
            actionable_statuses = (NODE_STATUS.READY, )

        node = factory.make_Node(status=NODE_STATUS.NEW)
        actions = compile_node_actions(
            node, factory.make_admin(), classes=[MyAction])
        self.assertEqual({}, actions)

    def test_compile_node_actions_checks_permission(self):

        class MyAction(FakeNodeAction):
            permission = NODE_PERMISSION.EDIT

        node = factory.make_Node(status=NODE_STATUS.COMMISSIONING)
        actions = compile_node_actions(
            node, factory.make_User(), classes=[MyAction])
        self.assertEqual({}, actions)

    def test_compile_node_actions_includes_inhibited_actions(self):

        class MyAction(FakeNodeAction):
            fake_inhibition = factory.make_string()

        actions = compile_node_actions(
            factory.make_Node(), factory.make_admin(), classes=[MyAction])
        self.assertEqual([MyAction.name], actions.keys())

    def test_compile_node_actions_maps_names(self):

        class Action1(FakeNodeAction):
            name = factory.make_string()

        class Action2(FakeNodeAction):
            name = factory.make_string()

        actions = compile_node_actions(
            factory.make_Node(), factory.make_admin(),
            classes=[Action1, Action2])
        for name, action in actions.items():
            self.assertEqual(name, action.name)

    def test_compile_node_actions_maintains_order(self):
        names = [factory.make_string() for counter in range(4)]
        classes = [
            type(b"Action%d" % counter, (FakeNodeAction,), {'name': name})
            for counter, name in enumerate(names)]
        actions = compile_node_actions(
            factory.make_Node(), factory.make_admin(), classes=classes)
        self.assertSequenceEqual(names, actions.keys())
        self.assertSequenceEqual(
            names, [action.name for action in actions.values()])

    def test_is_permitted_allows_if_user_has_permission(self):

        class MyAction(FakeNodeAction):
            permission = NODE_PERMISSION.EDIT

        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        self.assertTrue(MyAction(node, node.owner).is_permitted())

    def test_is_permitted_disallows_if_user_lacks_permission(self):

        class MyAction(FakeNodeAction):
            permission = NODE_PERMISSION.EDIT

        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        self.assertFalse(MyAction(node, factory.make_User()).is_permitted())

    def test_is_permitted_uses_installable_permission(self):

        class MyAction(FakeNodeAction):
            permission = NODE_PERMISSION.VIEW
            installable_permission = NODE_PERMISSION.EDIT

        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User())
        self.assertFalse(MyAction(node, factory.make_User()).is_permitted())

    def test_is_permitted_doest_use_installable_permission_if_device(self):

        class MyAction(FakeNodeAction):
            permission = NODE_PERMISSION.VIEW
            installable_permission = NODE_PERMISSION.EDIT

        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_User(),
            installable=False)
        self.assertTrue(MyAction(node, factory.make_User()).is_permitted())

    def test_inhibition_wraps_inhibit(self):
        inhibition = factory.make_string()
        action = FakeNodeAction(factory.make_Node(), factory.make_User())
        action.fake_inhibition = inhibition
        self.assertEqual(inhibition, action.inhibition)

    def test_inhibition_caches_inhibition(self):
        # The inhibition property will call inhibit() only once.  We can
        # prove this by changing the string inhibit() returns; it won't
        # affect the value of the property.
        inhibition = factory.make_string()
        action = FakeNodeAction(factory.make_Node(), factory.make_User())
        action.fake_inhibition = inhibition
        self.assertEqual(inhibition, action.inhibition)
        action.fake_inhibition = factory.make_string()
        self.assertEqual(inhibition, action.inhibition)

    def test_inhibition_caches_None(self):
        # An inhibition of None is also faithfully cached.  In other
        # words, it doesn't get mistaken for an uninitialized cache or
        # anything.
        action = FakeNodeAction(factory.make_Node(), factory.make_User())
        action.fake_inhibition = None
        self.assertIsNone(action.inhibition)
        action.fake_inhibition = factory.make_string()
        self.assertIsNone(action.inhibition)

    def test_installable_only_is_not_actionable_if_node_isnt_installable(self):
        status = NODE_STATUS.NEW
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner, status=status, installable=False)
        action = FakeNodeAction(node, owner)
        action.installable_only = True
        self.assertFalse(action.is_actionable())

    def test_installable_only_is_actionable_if_node_is_installable(self):
        status = NODE_STATUS.NEW
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner, status=status, installable=True)
        action = FakeNodeAction(node, owner)
        action.installable_only = True
        self.assertTrue(action.is_actionable())

    def test_is_actionable_checks_node_status_in_actionable_status(self):

        class MyAction(FakeNodeAction):
            actionable_statuses = [NODE_STATUS.ALLOCATED]

        node = factory.make_Node(status=NODE_STATUS.BROKEN)
        self.assertFalse(MyAction(node, factory.make_User()).is_actionable())


class TestDeleteAction(MAASServerTestCase):

    def test__deletes_node(self):
        node = factory.make_Node()
        action = Delete(node, factory.make_admin())
        action.execute()
        self.assertIsNone(reload_object(node))


class TestCommissionAction(MAASServerTestCase):

    scenarios = (
        ("NEW", {"status": NODE_STATUS.NEW}),
        ("FAILED_COMMISSIONING", {
            "status": NODE_STATUS.FAILED_COMMISSIONING}),
        ("READY", {"status": NODE_STATUS.READY}),
    )

    def test_Commission_starts_commissioning(self):
        node = factory.make_Node(
            mac=True, status=self.status,
            power_type='ether_wake')
        self.patch_autospec(node, 'start_transition_monitor')
        node_start = self.patch(node, 'start')
        node_start.side_effect = lambda user, user_data: post_commit()
        admin = factory.make_admin()
        action = Commission(node, admin)
        with post_commit_hooks:
            action.execute()
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)
        self.assertThat(
            node_start, MockCalledOnceWith(admin, user_data=ANY))


class TestAbortAction(MAASTransactionServerTestCase):

    def test_Abort_aborts_disk_erasing(self):
        with transaction.atomic():
            owner = factory.make_User()
            node = factory.make_Node(
                status=NODE_STATUS.DISK_ERASING, owner=owner)

        node_stop = self.patch_autospec(node, 'stop')
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()

        with post_commit_hooks:
            with transaction.atomic():
                Abort(node, owner).execute()

        with transaction.atomic():
            node = reload_object(node)
            self.assertEqual(NODE_STATUS.FAILED_DISK_ERASING, node.status)

        self.assertThat(node_stop, MockCalledOnceWith(owner))

    def test_Abort_aborts_commissioning(self):
        """Makes sure a COMMISSIONING node is returned to NEW status after an
        abort.
        """
        with transaction.atomic():
            node = factory.make_Node(
                mac=True, status=NODE_STATUS.COMMISSIONING,
                power_type='virsh')
            admin = factory.make_admin()

        self.patch_autospec(node, 'stop_transition_monitor')
        node_stop = self.patch_autospec(node, 'stop')
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()

        with post_commit_hooks:
            with transaction.atomic():
                Abort(node, admin).execute()

        with transaction.atomic():
            node = reload_object(node)
            self.assertEqual(NODE_STATUS.NEW, node.status)

        self.assertThat(node_stop, MockCalledOnceWith(admin))

    def test_Abort_aborts_deployment(self):
        """Makes sure a DEPLOYING node is returned to ALLOCATED status after an
        abort.
        """
        with transaction.atomic():
            node = factory.make_Node(
                mac=True, status=NODE_STATUS.DEPLOYING,
                power_type='virsh')
            admin = factory.make_admin()

        self.patch_autospec(node, 'stop_transition_monitor')
        node_stop = self.patch_autospec(node, 'stop')
        # Return a post-commit hook from Node.stop().
        node_stop.side_effect = lambda user: post_commit()

        with post_commit_hooks:
            with transaction.atomic():
                Abort(node, admin).execute()

        with transaction.atomic():
            node = reload_object(node)
            self.assertEqual(NODE_STATUS.ALLOCATED, node.status)

        self.assertThat(node_stop, MockCalledOnceWith(admin))


class TestAcquireNodeAction(MAASServerTestCase):

    def test_Acquire_acquires_node(self):
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.READY,
            power_type='ether_wake')
        user = factory.make_User()
        Acquire(node, user).execute()
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)
        self.assertEqual(user, node.owner)

    def test_Acquire_uses_node_acquire_lock(self):
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.READY,
            power_type='ether_wake')
        user = factory.make_User()
        node_acquire = self.patch(locks, 'node_acquire')
        Acquire(node, user).execute()
        self.assertThat(node_acquire.__enter__, MockCalledOnceWith())
        self.assertThat(
            node_acquire.__exit__, MockCalledOnceWith(None, None, None))


class TestDeployAction(MAASServerTestCase):

    def test_Deploy_inhibit_allows_user_with_SSH_key(self):
        user_with_key = factory.make_User()
        factory.make_SSHKey(user_with_key)
        self.assertIsNone(
            Deploy(factory.make_Node(), user_with_key).inhibit())

    def test_Deploy_inhibit_allows_user_without_SSH_key(self):
        user_without_key = factory.make_User()
        action = Deploy(factory.make_Node(), user_without_key)
        inhibition = action.inhibit()
        self.assertIsNone(inhibition)

    def test_Deploy_is_actionable_if_user_doesnt_have_ssh_keys(self):
        owner = factory.make_User()
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.ALLOCATED,
            power_type='ether_wake', owner=owner)
        self.assertTrue(Deploy(node, owner).is_actionable())

    def test_Deploy_is_actionable_if_user_has_ssh_keys(self):
        owner = factory.make_User()
        factory.make_SSHKey(owner)
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.ALLOCATED,
            power_type='ether_wake', owner=owner)
        self.assertTrue(Deploy(node, owner).is_actionable())

    def test_Deploy_starts_node(self):
        user = factory.make_User()
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.ALLOCATED,
            power_type='ether_wake', owner=user)
        node_start = self.patch(node, 'start')
        Deploy(node, user).execute()
        self.assertThat(
            node_start, MockCalledOnceWith(user))

    def test_Deploy_sets_osystem_and_series(self):
        user = factory.make_User()
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.ALLOCATED,
            power_type='ether_wake', owner=user)
        self.patch(node, 'start')
        osystem = make_osystem_with_releases(self)
        extra = {
            "osystem": osystem["name"],
            "distro_series": osystem["releases"][0]["name"],
        }
        Deploy(node, user).execute(**extra)
        self.expectThat(node.osystem, Equals(osystem["name"]))
        self.expectThat(
            node.distro_series, Equals(osystem["releases"][0]["name"]))

    def test_Deploy_doesnt_set_osystem_and_series_if_os_missing(self):
        user = factory.make_User()
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.ALLOCATED,
            power_type='ether_wake', owner=user)
        self.patch(node, 'start')
        osystem = make_osystem_with_releases(self)
        extra = {
            "distro_series": osystem["releases"][0]["name"],
        }
        Deploy(node, user).execute(**extra)
        self.expectThat(node.osystem, Equals(""))
        self.expectThat(node.distro_series, Equals(""))

    def test_Deploy_doesnt_set_osystem_and_series_if_series_missing(self):
        user = factory.make_User()
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.ALLOCATED,
            power_type='ether_wake', owner=user)
        self.patch(node, 'start')
        osystem = make_osystem_with_releases(self)
        extra = {
            "osystem": osystem["name"],
        }
        Deploy(node, user).execute(**extra)
        self.expectThat(node.osystem, Equals(""))
        self.expectThat(node.distro_series, Equals(""))

    def test_Deploy_allocates_node_if_node_not_already_allocated(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.READY)
        self.patch(node, 'start')
        action = Deploy(node, user)
        action.execute()

        self.assertEqual(user, node.owner)
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)


class TestDeployActionTransactional(MAASTransactionServerTestCase):
    '''The following TestDeployAction tests require
        MAASTransactionServerTestCase, and thus, have been separated
        from the TestDeployAction above.
    '''

    def test_Deploy_returns_error_when_no_more_static_IPs(self):
        user = factory.make_User()
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface(
            status=NODE_STATUS.ALLOCATED, power_type='ether_wake', owner=user,
            power_state=POWER_STATE.OFF)
        ngi = node.get_primary_mac().cluster_interface

        # Narrow the available IP range and pre-claim the only address.
        ngi.static_ip_range_high = ngi.static_ip_range_low
        ngi.save()
        with transaction.atomic():
            StaticIPAddress.objects.allocate_new(
                ngi.network, ngi.static_ip_range_low, ngi.static_ip_range_high,
                ngi.ip_range_low, ngi.ip_range_high)

        e = self.assertRaises(NodeActionError, Deploy(node, user).execute)
        self.expectThat(
            e.message, Equals(
                "%s: Failed to start, static IP addresses are exhausted." %
                node.hostname))
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)


class TestSetZoneAction(MAASServerTestCase):

    def test_SetZone_sets_zone(self):
        user = factory.make_User()
        zone1 = factory.make_Zone()
        zone2 = factory.make_Zone()
        node = factory.make_Node(status=NODE_STATUS.NEW, zone=zone1)
        action = SetZone(node, user)
        action.execute(zone_id=zone2.id)
        self.assertEqual(node.zone.id, zone2.id)


class TestPowerOnAction(MAASServerTestCase):

    def test_PowerOn_starts_node(self):
        user = factory.make_User()
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.ALLOCATED,
            power_type='ether_wake', owner=user)
        node_start = self.patch(node, 'start')
        PowerOn(node, user).execute()
        self.assertThat(
            node_start, MockCalledOnceWith(user))

    def test_PowerOn_requires_edit_permission(self):
        user = factory.make_User()
        node = factory.make_Node()
        self.assertFalse(
            user.has_perm(NODE_PERMISSION.EDIT, node))
        self.assertFalse(PowerOn(node, user).is_permitted())

    def test_PowerOn_is_actionable_if_node_doesnt_have_an_owner(self):
        owner = factory.make_User()
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.DEPLOYED,
            power_type='ether_wake')
        self.assertTrue(PowerOn(node, owner).is_actionable())

    def test_PowerOn_is_actionable_if_node_does_have_an_owner(self):
        owner = factory.make_User()
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.DEPLOYED,
            power_type='ether_wake', owner=owner)
        self.assertTrue(PowerOn(node, owner).is_actionable())


class TestPowerOffAction(MAASServerTestCase):

    def test__stops_deployed_node(self):
        user = factory.make_User()
        params = dict(
            power_address=factory.make_string(),
            power_user=factory.make_string(),
            power_pass=factory.make_string())
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.DEPLOYED,
            power_type='ipmi',
            owner=user, power_parameters=params)
        self.patch(node, 'start_transition_monitor')
        node_stop = self.patch_autospec(node, 'stop')

        PowerOff(node, user).execute()

        self.assertThat(node_stop, MockCalledOnceWith(user))

    def test__stops_Ready_node(self):
        admin = factory.make_admin()
        params = dict(
            power_address=factory.make_string(),
            power_user=factory.make_string(),
            power_pass=factory.make_string())
        node = factory.make_Node(
            mac=True, status=NODE_STATUS.READY,
            power_type='ipmi', power_parameters=params)
        node_stop = self.patch_autospec(node, 'stop')

        PowerOff(node, admin).execute()

        self.assertThat(node_stop, MockCalledOnceWith(admin))

    def test__actionable_for_non_monitored_states(self):
        all_statuses = NON_MONITORED_STATUSES
        results = {}
        for status in all_statuses:
            node = factory.make_Node(
                status=status, power_type='ipmi', power_state=POWER_STATE.ON)
            actions = compile_node_actions(
                node, factory.make_admin(), classes=[PowerOff])
            results[status] = actions.keys()
        expected_results = {status: [PowerOff.name] for status in all_statuses}
        self.assertEqual(
            expected_results, results,
            "Nodes with certain statuses could not be powered off.")

    def test__non_actionable_for_monitored_states(self):
        all_statuses = MONITORED_STATUSES
        results = {}
        for status in all_statuses:
            node = factory.make_Node(
                status=status, power_type='ipmi', power_state=POWER_STATE.ON)
            actions = compile_node_actions(
                node, factory.make_admin(), classes=[PowerOff])
            results[status] = actions.keys()
        expected_results = {status: [] for status in all_statuses}
        self.assertEqual(
            expected_results, results,
            "Nodes with certain statuses could be powered off.")

    def test__non_actionable_if_node_already_off(self):
        all_statuses = NON_MONITORED_STATUSES
        results = {}
        for status in all_statuses:
            node = factory.make_Node(
                status=status, power_type='ipmi', power_state=POWER_STATE.OFF)
            actions = compile_node_actions(
                node, factory.make_admin(), classes=[PowerOff])
            results[status] = actions.keys()
        expected_results = {status: [] for status in all_statuses}
        self.assertEqual(
            expected_results, results,
            "Nodes already powered off can be powered off.")


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
        user = factory.make_User()
        params = dict(
            power_address=factory.make_string(),
            power_user=factory.make_string(),
            power_pass=factory.make_string())
        node = factory.make_Node(
            mac=True, status=self.actionable_status,
            power_type='ipmi', power_state=POWER_STATE.ON,
            owner=user, power_parameters=params)
        self.patch(node, 'start_transition_monitor')
        node_stop = self.patch_autospec(node, 'stop')

        Release(node, user).execute()

        self.expectThat(node.status, Equals(NODE_STATUS.RELEASING))
        self.assertThat(
            node_stop, MockCalledOnceWith(user))


class TestMarkBrokenAction(MAASServerTestCase):

    def test_changes_status(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user, status=NODE_STATUS.COMMISSIONING)
        action = MarkBroken(node, user)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)

    def test_updates_error_description(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user, status=NODE_STATUS.COMMISSIONING)
        action = MarkBroken(node, user)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual(
            "Manually marked as broken by user '%s'" % user.username,
            reload_object(node).error_description
        )

    def test_requires_edit_permission(self):
        user = factory.make_User()
        node = factory.make_Node()
        self.assertFalse(MarkBroken(node, user).is_permitted())


class TestMarkFixedAction(MAASServerTestCase):

    def test_changes_status(self):
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, power_state=POWER_STATE.OFF)
        user = factory.make_admin()
        action = MarkFixed(node, user)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_raise_NodeActionError_if_on(self):
        node = factory.make_Node(
            status=NODE_STATUS.BROKEN, power_state=POWER_STATE.ON)
        user = factory.make_admin()
        action = MarkFixed(node, user)
        self.assertTrue(action.is_permitted())
        self.assertRaises(NodeActionError, action.execute)

    def test_requires_admin_permission(self):
        user = factory.make_User()
        node = factory.make_Node()
        self.assertFalse(MarkFixed(node, user).is_permitted())

    def test_not_enabled_if_not_broken(self):
        status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=[NODE_STATUS.BROKEN])
        node = factory.make_Node(status=status)
        actions = compile_node_actions(
            node, factory.make_admin(), classes=[MarkFixed])
        self.assertItemsEqual([], actions)


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
        if self.exception_class is MultipleFailures:
            exception = self.exception_class(
                Failure(Exception(factory.make_name("exception"))))
        elif self.exception_class is ExternalProcessError:
            exception = self.exception_class(
                1, ["cmd"], factory.make_name("exception"))
        else:
            exception = self.exception_class(factory.make_name("exception"))
        return exception

    def patch_rpc_methods(self, node):
        exception = self.make_exception()
        self.patch(node, 'start').side_effect = exception
        self.patch(node, 'stop').side_effect = exception
        self.patch_autospec(node, 'start_transition_monitor')
        self.patch_autospec(node, 'stop_transition_monitor')

    def make_action(self, action_class, node_status, power_state=None):
        node = factory.make_Node(
            mac=True, status=node_status, power_type='ether_wake',
            power_state=power_state)
        admin = factory.make_admin()
        return action_class(node, admin)

    def test_Commission_handles_rpc_errors(self):
        from maasserver import node_query
        self.addCleanup(node_query.enable)
        node_query.disable()

        action = self.make_action(Commission, NODE_STATUS.READY)
        self.patch_rpc_methods(action.node)
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(
                action.node.start.side_effect),
            unicode(exception))

    def test_Abort_handles_rpc_errors(self):
        action = self.make_action(
            Abort, NODE_STATUS.DISK_ERASING)
        self.patch_rpc_methods(action.node)
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(
                action.node.stop.side_effect),
            unicode(exception))

    def test_PowerOn_handles_rpc_errors(self):
        action = self.make_action(PowerOn, NODE_STATUS.READY)
        self.patch_rpc_methods(action.node)
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(
                action.node.start.side_effect),
            unicode(exception))

    def test_PowerOff_handles_rpc_errors(self):
        action = self.make_action(PowerOff, NODE_STATUS.DEPLOYED)
        self.patch_rpc_methods(action.node)
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(
                action.node.stop.side_effect),
            unicode(exception))

    def test_Release_handles_rpc_errors(self):
        action = self.make_action(
            Release, NODE_STATUS.ALLOCATED, power_state=POWER_STATE.ON)
        self.patch_rpc_methods(action.node)
        exception = self.assertRaises(NodeActionError, action.execute)
        self.assertEqual(
            get_error_message_for_exception(
                action.node.stop.side_effect),
            unicode(exception))
