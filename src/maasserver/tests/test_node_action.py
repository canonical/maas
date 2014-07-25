# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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

from urlparse import urlparse

from django.core.urlresolvers import reverse
from maasserver.enum import (
    NODE_BOOT,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    )
from maasserver.exceptions import (
    NodeActionError,
    Redirect,
    )
from maasserver.models import StaticIPAddress
from maasserver.node_action import (
    AbortCommissioning,
    Commission,
    compile_node_actions,
    Delete,
    MarkBroken,
    MarkFixed,
    NodeAction,
    StartNode,
    StopNode,
    UseCurtin,
    UseDI,
    )
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.power.poweraction import PowerAction


ALL_STATUSES = NODE_STATUS_CHOICES_DICT.keys()


class FakeNodeAction(NodeAction):
    name = "fake"
    display = "Action label"
    display_bulk = "Action label bulk"
    actionable_statuses = ALL_STATUSES
    permission = NODE_PERMISSION.VIEW

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
            factory.make_node(), factory.make_admin(), classes=[MyAction])
        self.assertEqual([MyAction.name], actions.keys())

    def test_compile_node_actions_checks_node_status(self):

        class MyAction(FakeNodeAction):
            actionable_statuses = (NODE_STATUS.READY, )

        node = factory.make_node(status=NODE_STATUS.DECLARED)
        actions = compile_node_actions(
            node, factory.make_admin(), classes=[MyAction])
        self.assertEqual({}, actions)

    def test_compile_node_actions_checks_permission(self):

        class MyAction(FakeNodeAction):
            permission = NODE_PERMISSION.EDIT

        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        actions = compile_node_actions(
            node, factory.make_user(), classes=[MyAction])
        self.assertEqual({}, actions)

    def test_compile_node_actions_includes_inhibited_actions(self):

        class MyAction(FakeNodeAction):
            fake_inhibition = factory.make_string()

        actions = compile_node_actions(
            factory.make_node(), factory.make_admin(), classes=[MyAction])
        self.assertEqual([MyAction.name], actions.keys())

    def test_compile_node_actions_maps_names(self):

        class Action1(FakeNodeAction):
            name = factory.make_string()

        class Action2(FakeNodeAction):
            name = factory.make_string()

        actions = compile_node_actions(
            factory.make_node(), factory.make_admin(),
            classes=[Action1, Action2])
        for name, action in actions.items():
            self.assertEqual(name, action.name)

    def test_compile_node_actions_maintains_order(self):
        names = [factory.make_string() for counter in range(4)]
        classes = [
            type(b"Action%d" % counter, (FakeNodeAction,), {'name': name})
            for counter, name in enumerate(names)]
        actions = compile_node_actions(
            factory.make_node(), factory.make_admin(), classes=classes)
        self.assertSequenceEqual(names, actions.keys())
        self.assertSequenceEqual(
            names, [action.name for action in actions.values()])

    def test_is_permitted_allows_if_user_has_permission(self):

        class MyAction(FakeNodeAction):
            permission = NODE_PERMISSION.EDIT

        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        self.assertTrue(MyAction(node, node.owner).is_permitted())

    def test_is_permitted_disallows_if_user_lacks_permission(self):

        class MyAction(FakeNodeAction):
            permission = NODE_PERMISSION.EDIT

        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        self.assertFalse(MyAction(node, factory.make_user()).is_permitted())

    def test_inhibition_wraps_inhibit(self):
        inhibition = factory.make_string()
        action = FakeNodeAction(factory.make_node(), factory.make_user())
        action.fake_inhibition = inhibition
        self.assertEqual(inhibition, action.inhibition)

    def test_inhibition_caches_inhibition(self):
        # The inhibition property will call inhibit() only once.  We can
        # prove this by changing the string inhibit() returns; it won't
        # affect the value of the property.
        inhibition = factory.make_string()
        action = FakeNodeAction(factory.make_node(), factory.make_user())
        action.fake_inhibition = inhibition
        self.assertEqual(inhibition, action.inhibition)
        action.fake_inhibition = factory.make_string()
        self.assertEqual(inhibition, action.inhibition)

    def test_inhibition_caches_None(self):
        # An inhibition of None is also faithfully cached.  In other
        # words, it doesn't get mistaken for an uninitialized cache or
        # anything.
        action = FakeNodeAction(factory.make_node(), factory.make_user())
        action.fake_inhibition = None
        self.assertIsNone(action.inhibition)
        action.fake_inhibition = factory.make_string()
        self.assertIsNone(action.inhibition)


class TestDeleteNodeAction(MAASServerTestCase):

    def test_Delete_inhibit_when_node_is_allocated(self):
        node = factory.make_node(status=NODE_STATUS.ALLOCATED)
        action = Delete(node, factory.make_admin())
        inhibition = action.inhibit()
        self.assertEqual(
            "You cannot delete this node because it's in use.", inhibition)

    def test_Delete_does_not_inhibit_otherwise(self):
        node = factory.make_node(status=NODE_STATUS.FAILED_TESTS)
        action = Delete(node, factory.make_admin())
        inhibition = action.inhibit()
        self.assertIsNone(inhibition)

    def test_Delete_redirects_to_node_delete_view(self):
        node = factory.make_node()
        action = Delete(node, factory.make_admin())
        try:
            action.execute()
        except Redirect as e:
            pass
        self.assertEqual(
            reverse('node-delete', args=[node.system_id]),
            urlparse(unicode(e)).path)


class TestCommissionNodeAction(MAASServerTestCase):

    def test_Commission_starts_commissioning(self):
        statuses = (
            NODE_STATUS.DECLARED, NODE_STATUS.FAILED_TESTS,
            NODE_STATUS.READY)
        for status in statuses:
            node = factory.make_node(
                mac=True, status=status,
                power_type='ether_wake')
            action = Commission(node, factory.make_admin())
            action.execute()
            self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)
            self.assertEqual(
                'provisioningserver.tasks.power_on',
                self.celery.tasks[0]['task'].name)


class TestAbortCommissioningNodeAction(MAASServerTestCase):

    def test_AbortCommissioning_aborts_commissioning(self):
        self.patch(PowerAction, 'run_shell').return_value = ('', '')
        node = factory.make_node(
            mac=True, status=NODE_STATUS.COMMISSIONING,
            power_type='virsh')
        action = AbortCommissioning(node, factory.make_admin())
        action.execute()
        self.assertEqual(NODE_STATUS.DECLARED, node.status)
        self.assertEqual(
            'provisioningserver.tasks.power_off',
            self.celery.tasks[0]['task'].name)


class TestStartNodeNodeAction(MAASServerTestCase):

    def test_StartNode_inhibit_allows_user_with_SSH_key(self):
        user_with_key = factory.make_user()
        factory.make_sshkey(user_with_key)
        self.assertIsNone(
            StartNode(factory.make_node(), user_with_key).inhibit())

    def test_StartNode_inhibit_disallows_user_without_SSH_key(self):
        user_without_key = factory.make_user()
        action = StartNode(factory.make_node(), user_without_key)
        inhibition = action.inhibit()
        self.assertIsNotNone(inhibition)
        self.assertIn("SSH key", inhibition)

    def test_StartNode_acquires_and_starts_node(self):
        node = factory.make_node(
            mac=True, status=NODE_STATUS.READY,
            power_type='ether_wake')
        user = factory.make_user()
        StartNode(node, user).execute()
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)
        self.assertEqual(user, node.owner)
        self.assertEqual(
            'provisioningserver.tasks.power_on',
            self.celery.tasks[0]['task'].name)

    def test_StartNode_returns_error_when_no_more_static_IPs(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface(
            status=NODE_STATUS.READY, power_type='ether_wake')
        ngi = node.get_primary_mac().cluster_interface

        # Narrow the available IP range and pre-claim the only address.
        ngi.static_ip_range_high = ngi.static_ip_range_low
        ngi.save()
        StaticIPAddress.objects.allocate_new(
            ngi.static_ip_range_high, ngi.static_ip_range_low)

        user = factory.make_user()
        e = self.assertRaises(NodeActionError, StartNode(node, user).execute)
        self.assertEqual(
            "%s: Failed to start, static IP addresses are exhausted." %
            node.hostname, e.message)
        self.assertEqual(NODE_STATUS.READY, node.status)


class TestStopNodeNodeAction(MAASServerTestCase):

    def test_StopNode_stops_and_releases_node(self):
        self.patch(PowerAction, 'run_shell', lambda *args, **kwargs: ('', ''))
        user = factory.make_user()
        params = dict(
            power_address=factory.make_string(),
            power_user=factory.make_string(),
            power_pass=factory.make_string())
        node = factory.make_node(
            mac=True, status=NODE_STATUS.ALLOCATED,
            power_type='ipmi',
            owner=user, power_parameters=params)
        StopNode(node, user).execute()

        self.assertEqual(NODE_STATUS.READY, node.status)
        self.assertIsNone(node.owner)
        self.assertEqual(
            'provisioningserver.tasks.power_off',
            self.celery.tasks[0]['task'].name)


class TestUseCurtinNodeAction(MAASServerTestCase):

    def test_sets_boot_type(self):
        user = factory.make_user()
        node = factory.make_node(owner=user, boot_type=NODE_BOOT.DEBIAN)
        action = UseCurtin(node, user)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual(NODE_BOOT.FASTPATH, node.boot_type)

    def test_requires_edit_permission(self):
        user = factory.make_user()
        node = factory.make_node(boot_type=NODE_BOOT.DEBIAN)
        self.assertFalse(UseCurtin(node, user).is_permitted())

    def test_not_permitted_if_already_uses_curtin(self):
        node = factory.make_node(boot_type=NODE_BOOT.FASTPATH)
        user = factory.make_admin()
        self.assertFalse(UseCurtin(node, user).is_permitted())


class TestUseDINodeAction(MAASServerTestCase):

    def test_sets_boot_type(self):
        user = factory.make_user()
        node = factory.make_node(owner=user, boot_type=NODE_BOOT.FASTPATH)
        action = UseDI(node, user)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual(NODE_BOOT.DEBIAN, node.boot_type)

    def test_requires_edit_permission(self):
        user = factory.make_user()
        node = factory.make_node(boot_type=NODE_BOOT.FASTPATH)
        self.assertFalse(UseDI(node, user).is_permitted())

    def test_not_permitted_if_already_uses_di(self):
        node = factory.make_node(boot_type=NODE_BOOT.DEBIAN)
        user = factory.make_admin()
        self.assertFalse(UseDI(node, user).is_permitted())


class TestMarkBrokenAction(MAASServerTestCase):

    def test_changes_status(self):
        user = factory.make_user()
        node = factory.make_node(owner=user, status=NODE_STATUS.COMMISSIONING)
        action = MarkBroken(node, user)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual(NODE_STATUS.BROKEN, reload_object(node).status)

    def test_updates_error_description(self):
        user = factory.make_user()
        node = factory.make_node(owner=user, status=NODE_STATUS.COMMISSIONING)
        action = MarkBroken(node, user)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual(
            "Manually marked as broken by user '%s'" % user.username,
            reload_object(node).error_description
        )

    def test_requires_edit_permission(self):
        user = factory.make_user()
        node = factory.make_node()
        self.assertFalse(MarkBroken(node, user).is_permitted())


class TestMarkFixedAction(MAASServerTestCase):

    def test_changes_status(self):
        node = factory.make_node(status=NODE_STATUS.BROKEN)
        user = factory.make_admin()
        action = MarkFixed(node, user)
        self.assertTrue(action.is_permitted())
        action.execute()
        self.assertEqual(NODE_STATUS.READY, reload_object(node).status)

    def test_requires_admin_permission(self):
        user = factory.make_user()
        node = factory.make_node()
        self.assertFalse(MarkFixed(node, user).is_permitted())

    def test_not_enabled_if_not_broken(self):
        status = factory.pick_choice(
            NODE_STATUS_CHOICES, but_not=[NODE_STATUS.BROKEN])
        node = factory.make_node(status=status)
        actions = compile_node_actions(
            node, factory.make_admin(), classes=[MarkFixed])
        self.assertItemsEqual([], actions)
