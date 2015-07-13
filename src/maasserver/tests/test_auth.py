# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

"""Test permissions."""

str = None

__metaclass__ = type
__all__ = []

import httplib

from django.core.urlresolvers import reverse
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
)
from maasserver.models import (
    MAASAuthorizationBackend,
    Node,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.nodeinituser import get_node_init_user


class LoginLogoutTest(MAASServerTestCase):

    def make_user(self, name='test', password='test'):
        """Create a user with a password."""
        return factory.make_User(username=name, password=password)

    def test_login(self):
        name = factory.make_string()
        password = factory.make_string()
        user = self.make_user(name, password)
        response = self.client.post(
            reverse('login'), {'username': name, 'password': password})

        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertEqual(user.id, self.client.session['_auth_user_id'])

    def test_login_failed(self):
        response = self.client.post(
            reverse('login'), {
                'username': factory.make_string(),
                'password': factory.make_string(),
                })

        self.assertEqual(httplib.OK, response.status_code)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout(self):
        name = factory.make_string()
        password = factory.make_string()
        factory.make_User(name, password)
        self.client.login(username=name, password=password)
        self.client.post(reverse('logout'))

        self.assertNotIn('_auth_user_id', self.client.session)


def make_unallocated_node():
    """Return a node that is not allocated to anyone."""
    return factory.make_Node()


def make_allocated_node(owner=None):
    """Create a node, owned by `owner` (or create owner if not given)."""
    if owner is None:
        owner = factory.make_User()
    return factory.make_Node(owner=owner, status=NODE_STATUS.ALLOCATED)


class TestMAASAuthorizationBackend(MAASServerTestCase):

    def test_invalid_check_object(self):
        backend = MAASAuthorizationBackend()
        mac = make_unallocated_node().add_mac_address('AA:BB:CC:DD:EE:FF')
        self.assertRaises(
            NotImplementedError, backend.has_perm,
            factory.make_admin(), NODE_PERMISSION.VIEW, mac)

    def test_invalid_check_permission(self):
        backend = MAASAuthorizationBackend()
        self.assertRaises(
            NotImplementedError, backend.has_perm,
            factory.make_admin(), 'not-access', make_unallocated_node())

    def test_node_init_user_cannot_access(self):
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(
            get_node_init_user(), NODE_PERMISSION.VIEW,
            make_unallocated_node()))

    def test_user_can_view_unowned_node(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(
            factory.make_User(), NODE_PERMISSION.VIEW,
            make_unallocated_node()))

    def test_user_can_view_nodes_owned_by_others(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(
            factory.make_User(), NODE_PERMISSION.VIEW, make_allocated_node()))

    def test_owned_status(self):
        # A non-admin user can access nodes he owns.
        backend = MAASAuthorizationBackend()
        node = make_allocated_node()
        self.assertTrue(
            backend.has_perm(
                node.owner, NODE_PERMISSION.VIEW, node))

    def test_user_cannot_edit_nodes_owned_by_others(self):
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(
            factory.make_User(), NODE_PERMISSION.EDIT, make_allocated_node()))

    def test_user_cannot_edit_unowned_node(self):
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(
            factory.make_User(), NODE_PERMISSION.EDIT,
            make_unallocated_node()))

    def test_user_can_edit_his_own_nodes(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertTrue(backend.has_perm(
            user, NODE_PERMISSION.EDIT, make_allocated_node(owner=user)))

    def test_user_has_no_admin_permission_on_node(self):
        # NODE_PERMISSION.ADMIN permission on nodes is granted to super users
        # only.
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NODE_PERMISSION.ADMIN, factory.make_Node()))

    def test_user_cannot_view_BlockDevice_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        device = factory.make_BlockDevice(node=node)
        self.assertFalse(backend.has_perm(user, NODE_PERMISSION.VIEW, device))

    def test_user_can_view_BlockDevice_when_no_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.VIEW, device))

    def test_user_can_view_BlockDevice_when_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        device = factory.make_BlockDevice(node=node)
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.VIEW, device))

    def test_user_cannot_edit_BlockDevice_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        device = factory.make_BlockDevice(node=node)
        self.assertFalse(backend.has_perm(user, NODE_PERMISSION.EDIT, device))

    def test_user_can_edit_VirtualBlockDevice_when_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        device = factory.make_VirtualBlockDevice(node=node)
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.EDIT, device))

    def test_user_has_no_admin_permission_on_BlockDevice(self):
        # NODE_PERMISSION.ADMIN permission on block devices is granted to super
        # user only.
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NODE_PERMISSION.ADMIN, factory.make_BlockDevice()))

    def test_user_cannot_view_FilesystemGroup_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.assertFalse(
            backend.has_perm(user, NODE_PERMISSION.VIEW, filesystem_group))

    def test_user_can_view_FilesystemGroup_when_no_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.assertTrue(
            backend.has_perm(user, NODE_PERMISSION.VIEW, filesystem_group))

    def test_user_can_view_FilesystemGroup_when_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.assertTrue(
            backend.has_perm(user, NODE_PERMISSION.VIEW, filesystem_group))

    def test_user_cannot_edit_FilesystemGroup_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.assertFalse(
            backend.has_perm(user, NODE_PERMISSION.EDIT, filesystem_group))

    def test_user_has_no_admin_permission_on_FilesystemGroup(self):
        # NODE_PERMISSION.ADMIN permission on block devices is granted to super
        # user only.
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NODE_PERMISSION.ADMIN, factory.make_FilesystemGroup()))


class TestNodeVisibility(MAASServerTestCase):

    def test_admin_sees_all_nodes(self):
        nodes = [
            make_allocated_node(),
            make_unallocated_node(),
            ]
        self.assertItemsEqual(
            nodes,
            Node.objects.get_nodes(
                factory.make_admin(), NODE_PERMISSION.VIEW))

    def test_user_sees_own_nodes_and_unowned_nodes(self):
        user = factory.make_User()
        make_allocated_node()
        own_node = make_allocated_node(owner=user)
        unowned_node = make_unallocated_node()
        self.assertItemsEqual(
            [own_node, unowned_node],
            Node.objects.get_nodes(own_node.owner, NODE_PERMISSION.VIEW))
