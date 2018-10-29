# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test permissions."""

__all__ = []

from functools import partial
import http.client

from maasserver.enum import (
    INTERFACE_TYPE,
    NODE_PERMISSION,
    NODE_STATUS,
)
from maasserver.middleware import ExternalAuthInfoMiddleware
from maasserver.models import (
    Config,
    MAASAuthorizationBackend,
    Node,
)
from maasserver.rbac import (
    FakeRBACClient,
    rbac,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.django_urls import reverse
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

        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertEqual(user.id, int(self.client.session['_auth_user_id']))

    def test_login_failed(self):
        response = self.client.post(
            reverse('login'), {
                'username': factory.make_string(),
                'password': factory.make_string(),
                })

        self.assertEqual(http.client.OK, response.status_code)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout(self):
        name = factory.make_string()
        password = factory.make_string()
        factory.make_User(name, password)
        self.client.login(username=name, password=password)
        self.client.post(reverse('logout'))

        self.assertNotIn('_auth_user_id', self.client.session)


def make_allocated_node(owner=None):
    """Create a node, owned by `owner` (or create owner if not given)."""
    if owner is None:
        owner = factory.make_User()
    return factory.make_Node(owner=owner, status=NODE_STATUS.ALLOCATED)


class TestMAASAuthorizationBackend(MAASServerTestCase):

    def enable_rbac(self):
        Config.objects.set_config('rbac_url', 'http://rbac.example.com')
        client = FakeRBACClient()
        rbac._store.client = client
        rbac._store.cleared = False  # Prevent re-creation of the client
        self.rbac_store = client.store

    def test_invalid_check_object(self):
        backend = MAASAuthorizationBackend()
        exc = factory.make_exception()
        self.assertRaises(
            NotImplementedError, backend.has_perm,
            factory.make_admin(), NODE_PERMISSION.VIEW, exc)

    def test_invalid_check_permission(self):
        backend = MAASAuthorizationBackend()
        self.assertRaises(
            NotImplementedError, backend.has_perm,
            factory.make_admin(), 'not-access', factory.make_Node())

    def test_node_init_user_cannot_access(self):
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(
            get_node_init_user(), NODE_PERMISSION.VIEW,
            factory.make_Node()))

    def test_user_can_view_unowned_node(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(
            factory.make_User(), NODE_PERMISSION.VIEW,
            factory.make_Node()))

    def test_user_cannot_view_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NODE_PERMISSION.VIEW, node))

    def test_user_cannot_view_node_other_pool(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        pool = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool)
        self.rbac_store.allow(user.username, pool, 'view')
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NODE_PERMISSION.VIEW, node))

    def test_user_can_view_unowned_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'view')
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.VIEW, node))

    def test_user_can_view_unowned_node_rbac_with_admin(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'admin-machines')
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.VIEW, node))

    def test_user_can_view_owned_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'view')
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.VIEW, node))

    def test_user_can_view_device_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Device()
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.VIEW, node))

    def test_user_can_edit_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'admin-machines')
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.EDIT, node))

    def test_user_cannot_edit_node_rbac_vith_view(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'view')
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NODE_PERMISSION.EDIT, node))

    def test_user_can_edit_owned_node_rbac_vith_admin(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'admin-machines')
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.EDIT, node))

    def test_user_cannot_edit_node_rbac_if_locked(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(locked=True)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'admin-machine')
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NODE_PERMISSION.EDIT, node))

    def test_user_cannot_edit_device_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Device()
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NODE_PERMISSION.EDIT, node))

    def test_user_can_view_nodes_owned_by_others(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(
            factory.make_User(), NODE_PERMISSION.VIEW, make_allocated_node()))

    def test_user_can_view_locked_node(self):
        backend = MAASAuthorizationBackend()
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner, status=NODE_STATUS.DEPLOYED, locked=True)
        self.assertTrue(backend.has_perm(owner, NODE_PERMISSION.VIEW, node))

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
            factory.make_Node()))

    def test_user_can_edit_his_own_nodes(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertTrue(backend.has_perm(
            user, NODE_PERMISSION.EDIT, make_allocated_node(owner=user)))

    def test_user_cannot_edit_locked_node(self):
        backend = MAASAuthorizationBackend()
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner, status=NODE_STATUS.DEPLOYED, locked=True)
        self.assertFalse(backend.has_perm(owner, NODE_PERMISSION.EDIT, node))

    def test_user_can_lock_locked_node(self):
        backend = MAASAuthorizationBackend()
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner, status=NODE_STATUS.DEPLOYED, locked=True)
        self.assertTrue(backend.has_perm(owner, NODE_PERMISSION.LOCK, node))

    def test_user_can_lock_owned_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'view')
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.LOCK, node))

    def test_user_cannot_lock_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'view')
        self.assertFalse(backend.has_perm(user, NODE_PERMISSION.LOCK, node))

    def test_user_can_lock_node_rbac_owner_other_user(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'admin-machines')
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.LOCK, node))

    def test_user_cannot_lock_node_rbac_owner_other_user(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'view')
        self.assertFalse(backend.has_perm(user, NODE_PERMISSION.LOCK, node))

    def test_user_has_no_admin_permission_on_node(self):
        # NODE_PERMISSION.ADMIN permission on nodes is granted to super users
        # only.
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NODE_PERMISSION.ADMIN, factory.make_Node()))

    def test_user_has_admin_permission_on_node_with_rbac(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, 'admin-machines')
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.ADMIN, node))

    def test_admin_has_admin_permission_on_node_with_rbac(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        user = factory.make_admin()
        node = factory.make_Node()
        self.assertTrue(backend.has_perm(user, NODE_PERMISSION.ADMIN, node))

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

    def test_authenticate_username_password(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        backend = MAASAuthorizationBackend()
        request = factory.make_fake_request('/')
        ExternalAuthInfoMiddleware(lambda request: request)(request)
        self.assertEqual(
            backend.authenticate(
                request, username=user.username, password=password),
            user)

    def test_authenticate_username_password_external_auth(self):
        Config.objects.set_config('external_auth_url', 'https://example.com')
        password = factory.make_string()
        user = factory.make_User(password=password)
        backend = MAASAuthorizationBackend()
        request = factory.make_fake_request('/')
        ExternalAuthInfoMiddleware(lambda request: request)(request)
        self.assertIsNone(
            backend.authenticate(
                request, username=user.username, password=password))

    def test_authenticate_external_user_denied(self):
        password = factory.make_string()
        user = factory.make_User(password=password, is_local=False)
        backend = MAASAuthorizationBackend()
        request = factory.make_fake_request('/')
        self.assertIsNone(
            backend.authenticate(
                request, username=user.username, password=password))


class TestMAASAuthorizationBackendForDeviceInterface(MAASServerTestCase):

    def test_owner_can_edit_device_interface(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        parent = factory.make_Node()
        device = factory.make_Device(
            owner=user, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device)
        self.assertTrue(
            backend.has_perm(
                user, NODE_PERMISSION.EDIT, interface))

    def test_non_owner_cannot_edit_device_interface(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        owner = factory.make_User()
        parent = factory.make_Node()
        device = factory.make_Device(
            owner=owner, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device)
        self.assertFalse(
            backend.has_perm(
                user, NODE_PERMISSION.EDIT, interface))


class TestMAASAuthorizationBackendForUnrestrictedRead(MAASServerTestCase):

    scenarios = (
        ("dnsdata", {"factory": factory.make_DNSData}),
        ("dnsresource", {"factory": factory.make_DNSResource}),
        ("domain", {"factory": factory.make_Domain}),
        ("fabric", {"factory": factory.make_Fabric}),
        ("interface", {
            "factory": partial(
                factory.make_Interface, INTERFACE_TYPE.PHYSICAL)}),
        ("subnet", {"factory": factory.make_Subnet}),
        ("space", {"factory": factory.make_Space}),
        ("staticroute", {"factory": factory.make_StaticRoute}),
        ("vlan", {"factory": factory.make_VLAN}),
        )

    def test_user_can_view(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertTrue(
            backend.has_perm(
                user, NODE_PERMISSION.VIEW, self.factory()))

    def test_user_cannot_edit(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NODE_PERMISSION.EDIT, self.factory()))

    def test_user_not_admin(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NODE_PERMISSION.ADMIN, self.factory()))

    def test_admin_can_view(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(
                admin, NODE_PERMISSION.VIEW, self.factory()))

    def test_admin_can_edit(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(
                admin, NODE_PERMISSION.EDIT, self.factory()))

    def test_admin_is_admin(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(
                admin, NODE_PERMISSION.ADMIN, self.factory()))


class TestMAASAuthorizationBackendForAdminRestricted(MAASServerTestCase):

    scenarios = (
        ("discovery", {"factory": factory.make_Discovery}),
        )

    def test_user_cannot_view(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NODE_PERMISSION.VIEW, self.factory()))

    def test_user_cannot_edit(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NODE_PERMISSION.EDIT, self.factory()))

    def test_user_not_admin(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NODE_PERMISSION.ADMIN, self.factory()))

    def test_admin_can_view(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(
                admin, NODE_PERMISSION.VIEW, self.factory()))

    def test_admin_can_edit(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(
                admin, NODE_PERMISSION.EDIT, self.factory()))

    def test_admin_is_admin(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(
                admin, NODE_PERMISSION.ADMIN, self.factory()))


class TestNodeVisibility(MAASServerTestCase):

    def test_admin_sees_all_nodes(self):
        nodes = [
            make_allocated_node(),
            factory.make_Node(),
            ]
        self.assertItemsEqual(
            nodes,
            Node.objects.get_nodes(
                factory.make_admin(), NODE_PERMISSION.VIEW))

    def test_user_sees_own_nodes_and_unowned_nodes(self):
        user = factory.make_User()
        own_node = make_allocated_node(owner=user)
        make_allocated_node()
        unowned_node = factory.make_Node()
        self.assertItemsEqual(
            [own_node, unowned_node],
            Node.objects.get_nodes(own_node.owner, NODE_PERMISSION.VIEW))
