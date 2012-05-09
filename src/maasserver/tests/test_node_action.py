# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for node actions."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from urlparse import urlparse

from django.core.urlresolvers import reverse
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    )
from maasserver.exceptions import Redirect
from maasserver.node_action import (
    AcceptAndCommission,
    compile_node_actions,
    Delete,
    NodeAction,
    RetryCommissioning,
    StartNode,
    )
from maasserver.provisioning import get_provisioning_api_proxy
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase


ALL_STATUSES = NODE_STATUS_CHOICES_DICT.keys()


class FakeNodeAction(NodeAction):
    display = "Action label"
    actionable_statuses = ALL_STATUSES
    permission = NODE_PERMISSION.VIEW

    # For testing: an inhibition for inhibit() to return.
    fake_inhibition = None

    def inhibit(self):
        return self.fake_inhibition

    def execute(self):
        pass


class TestNodeAction(TestCase):

    def test_compile_node_actions_returns_available_actions(self):

        class MyAction(FakeNodeAction):
            display = factory.getRandomString()

        actions = compile_node_actions(
            factory.make_node(), factory.make_admin(), classes=[MyAction])
        self.assertEqual([MyAction.display], actions.keys())

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
            fake_inhibition = factory.getRandomString()

        actions = compile_node_actions(
            factory.make_node(), factory.make_admin(), classes=[MyAction])
        self.assertEqual([MyAction.display], actions.keys())

    def test_compile_node_actions_maps_display_names(self):

        class Action1(FakeNodeAction):
            display = factory.getRandomString()

        class Action2(FakeNodeAction):
            display = factory.getRandomString()

        actions = compile_node_actions(
            factory.make_node(), factory.make_admin(),
            classes=[Action1, Action2])
        for label, action in actions.items():
            self.assertEqual(label, action.display)

    def test_compile_node_actions_maintains_order(self):
        labels = [factory.getRandomString() for counter in range(4)]
        classes = [
            type(b"Action%d" % counter, (FakeNodeAction,), {'display': label})
            for counter, label in enumerate(labels)]
        actions = compile_node_actions(
            factory.make_node(), factory.make_admin(), classes=classes)
        self.assertSequenceEqual(labels, actions.keys())
        self.assertSequenceEqual(
            labels, [action.display for action in actions.values()])

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
        inhibition = factory.getRandomString()
        action = FakeNodeAction(factory.make_node(), factory.make_user())
        action.fake_inhibition = inhibition
        self.assertEqual(inhibition, action.inhibition)

    def test_inhibition_caches_inhibition(self):
        # The inhibition property will call inhibit() only once.  We can
        # prove this by changing the string inhibit() returns; it won't
        # affect the value of the property.
        inhibition = factory.getRandomString()
        action = FakeNodeAction(factory.make_node(), factory.make_user())
        action.fake_inhibition = inhibition
        self.assertEqual(inhibition, action.inhibition)
        action.fake_inhibition = factory.getRandomString()
        self.assertEqual(inhibition, action.inhibition)

    def test_inhibition_caches_None(self):
        # An inhibition of None is also faithfully cached.  In other
        # words, it doesn't get mistaken for an uninitialized cache or
        # anything.
        action = FakeNodeAction(factory.make_node(), factory.make_user())
        action.fake_inhibition = None
        self.assertIsNone(action.inhibition)
        action.fake_inhibition = factory.getRandomString()
        self.assertIsNone(action.inhibition)

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

    def test_AcceptAndCommission_starts_commissioning(self):
        node = factory.make_node(status=NODE_STATUS.DECLARED)
        action = AcceptAndCommission(node, factory.make_admin())
        action.execute()
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)
        self.assertEqual(
            'start',
            get_provisioning_api_proxy().power_status.get(node.system_id))

    def test_RetryCommissioning_starts_commissioning(self):
        node = factory.make_node(status=NODE_STATUS.FAILED_TESTS)
        action = RetryCommissioning(node, factory.make_admin())
        action.execute()
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)
        self.assertEqual(
            'start',
            get_provisioning_api_proxy().power_status.get(node.system_id))

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
        node = factory.make_node(status=NODE_STATUS.READY)
        user = factory.make_user()
        StartNode(node, user).execute()
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)
        self.assertEqual(user, node.owner)
        self.assertEqual(
            'start',
            get_provisioning_api_proxy().power_status.get(node.system_id))
