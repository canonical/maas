# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Test permissions."""

__metaclass__ = type
__all__ = []

import httplib

from django.core.urlresolvers import reverse
from maasserver.models import (
    MaaSAuthorizationBackend,
    Node,
    NODE_STATUS,
    )
from maasserver.testing.factory import factory
from maastesting import TestCase


class LoginLogoutTest(TestCase):

    def setUp(self):
        super(LoginLogoutTest, self).setUp()
        self.user = factory.make_user(username='test', password='test')

    def test_login(self):
        response = self.client.post(
            reverse('login'), {'username': 'test', 'password': 'test'})

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(self.user.id, self.client.session['_auth_user_id'])

    def test_login_failed(self):
        response = self.client.post(
            reverse('login'), {'username': 'test', 'password': 'wrong-pw'})

        self.assertEqual(httplib.OK, response.status_code)
        self.assertNotIn('_auth_user_id', self.client.session.keys())

    def test_logout(self):
        self.user = factory.make_user(username='user', password='test')
        self.client.login(username='user', password='test')
        self.client.post(reverse('logout'))

        self.assertNotIn('_auth_user_id', self.client.session.keys())


class AuthTestMixin(object):

    def setUp(self):
        super(AuthTestMixin, self).setUp()
        self.backend = MaaSAuthorizationBackend()
        self.admin = factory.make_admin()
        self.user1 = factory.make_user(username='user1')
        self.user2 = factory.make_user(username='user2')
        self.node_user1 = factory.make_node(
            owner=self.user1, status=NODE_STATUS.DEPLOYED)
        self.node_user2 = factory.make_node(
            owner=self.user2, status=NODE_STATUS.DEPLOYED)
        self.not_owned_node = factory.make_node()


class TestMaaSAuthorizationBackend(AuthTestMixin, TestCase):

    def test_invalid_check_object(self):
        mac = self.not_owned_node.add_mac_address('AA:BB:CC:DD:EE:FF')
        self.assertRaises(
            NotImplementedError, self.backend.has_perm,
            self.admin, 'access', mac)

    def test_invalid_check_permission(self):
        self.assertRaises(
            NotImplementedError, self.backend.has_perm,
            self.admin, 'not-access', self.not_owned_node)

    def test_not_owned_status(self):
        # A non-admin user can access a node that is not yet owned.
        self.assertTrue(self.backend.has_perm(
            self.user1, 'access', self.not_owned_node))

    def test_owned_status_others(self):
        # A non-admin user cannot access nodes owned by other people.
        self.assertFalse(self.backend.has_perm(
            self.user2, 'access', self.node_user1))

    def test_owned_status(self):
        # A non-admin user can access nodes he owns.
        self.assertTrue(self.backend.has_perm(
            self.user1, 'access', self.node_user1))


class TestNodeVisibility(AuthTestMixin, TestCase):

    def test_nodes_admin_access(self):
        # An admin sees all the nodes.
        self.assertSequenceEqual(
            [self.node_user1, self.node_user2, self.not_owned_node],
            Node.objects.get_visible_nodes(self.admin))

    def test_nodes_not_owned_status(self):
        # A non-admin user only has access to non-owned nodes and his own
        # nodes.
        self.assertSequenceEqual(
            [self.node_user1, self.not_owned_node],
            Node.objects.get_visible_nodes(self.user1))
