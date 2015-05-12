# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `NodeActionForm`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from django.contrib import messages
from maasserver.enum import (
    NODE_BOOT,
    NODE_STATUS,
    POWER_STATE,
)
from maasserver.exceptions import NodeActionError
from maasserver.forms import (
    get_action_form,
    NodeActionForm,
)
from maasserver.node_action import (
    Commission,
    Delete,
    Deploy,
    MarkBroken,
    PowerOff,
    SetZone,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks


class TestNodeActionForm(MAASServerTestCase):

    def test_get_action_form_creates_form_class_with_attributes(self):
        user = factory.make_admin()
        form_class = get_action_form(user)

        self.assertEqual(user, form_class.user)

    def test_get_action_form_creates_form_class(self):
        user = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        form = get_action_form(user)(node)

        self.assertIsInstance(form, NodeActionForm)
        self.assertEqual(node, form.node)

    def test_get_action_form_for_admin(self):
        """Check the actions available to admins"""
        admin = factory.make_admin()
        node = factory.make_Node(
            status=NODE_STATUS.NEW, boot_type=NODE_BOOT.DEBIAN,
            power_state=POWER_STATE.ON)
        form = get_action_form(admin)(node)

        self.assertItemsEqual(
            [
                Commission.name,
                Delete.name,
                MarkBroken.name,
                SetZone.name,
                PowerOff.name,
            ],
            form.actions)

    def test_get_action_form_for_user(self):
        """Check the actions available to users"""
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        form = get_action_form(user)(node)

        self.assertIsInstance(form, NodeActionForm)
        self.assertEqual(node, form.node)
        self.assertItemsEqual({}, form.actions)

    def test_save_performs_requested_action(self):
        admin = factory.make_admin()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        form = get_action_form(admin)(
            node, {NodeActionForm.input_name: Commission.name})
        self.assertTrue(form.is_valid())
        with post_commit_hooks:
            form.save()
        self.assertEqual(NODE_STATUS.COMMISSIONING, node.status)

    def test_rejects_disallowed_action(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        form = get_action_form(user)(
            node, {NodeActionForm.input_name: Commission.name})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'action': ['Not a permitted action: %s.' % Commission.name]},
            form._errors)

    def test_rejects_unknown_action(self):
        user = factory.make_User()
        node = factory.make_Node(status=NODE_STATUS.NEW)
        action = factory.make_string()
        form = get_action_form(user)(
            node, {NodeActionForm.input_name: action})
        self.assertFalse(form.is_valid())
        self.assertIn(
            "is not one of the available choices.", form._errors['action'][0])

    def test_shows_error_message_for_NodeActionError(self):
        error_text = factory.make_string(prefix="NodeActionError")
        exc = NodeActionError(error_text)
        self.patch(Deploy, "execute").side_effect = exc
        user = factory.make_User()
        factory.make_SSHKey(user)
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, owner=user)
        action = Deploy.name
        # Required for messages to work:
        request = factory.make_fake_request("/fake")
        form = get_action_form(user, request)(
            node, {NodeActionForm.input_name: action})
        form.save()
        [observed] = messages.get_messages(form.request)
        expected = (messages.ERROR, error_text, '')
        self.assertEqual(expected, observed)
