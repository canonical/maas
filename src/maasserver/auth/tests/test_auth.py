# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from functools import partial
import http.client

from django.urls import reverse

from maasserver.auth import MAASAuthorizationBackend
from maasserver.enum import INTERFACE_TYPE, NODE_STATUS
from maasserver.middleware import ExternalAuthInfoMiddleware
from maasserver.models import Node
from maasserver.permissions import (
    NodePermission,
    PodPermission,
    ResourcePoolPermission,
)
from maasserver.rbac import ALL_RESOURCES, FakeRBACClient, rbac
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.nodeinituser import get_node_init_user


class TestLoginLogout(MAASServerTestCase):
    def make_user(self, name="test", password="test"):
        """Create a user with a password."""
        return factory.make_User(username=name, password=password)

    def test_login(self):
        name = factory.make_string()
        password = factory.make_string()
        user = self.make_user(name, password)
        response = self.client.post(
            reverse("login"), {"username": name, "password": password}
        )

        self.assertEqual(http.client.NO_CONTENT, response.status_code)
        self.assertEqual(user.id, int(self.client.session["_auth_user_id"]))

    def test_login_failed(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": factory.make_string(),
                "password": factory.make_string(),
            },
        )

        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout(self):
        name = factory.make_string()
        password = factory.make_string()
        factory.make_User(name, password)
        self.client.login(username=name, password=password)
        self.client.post(reverse("logout"))

        self.assertNotIn("_auth_user_id", self.client.session)


def make_allocated_node(owner=None):
    """Create a node, owned by `owner` (or create owner if not given)."""
    if owner is None:
        owner = factory.make_User()
    return factory.make_Node(owner=owner, status=NODE_STATUS.ALLOCATED)


class EnableRBACMixin:
    def enable_rbac(self):
        SecretManager().set_composite_secret(
            "external-auth", {"rbac-url": "https://rbac.example.com"}
        )
        client = FakeRBACClient()
        rbac._store.client = client
        rbac._store.cleared = False  # Prevent re-creation of the client
        self.rbac_store = client.store


class TestMAASAuthorizationBackend(MAASServerTestCase, EnableRBACMixin):
    def test_invalid_check_object(self):
        backend = MAASAuthorizationBackend()
        exc = factory.make_exception()
        self.assertRaises(
            NotImplementedError,
            backend.has_perm,
            factory.make_admin(),
            NodePermission.view,
            exc,
        )

    def test_invalid_check_permission(self):
        backend = MAASAuthorizationBackend()
        self.assertRaises(
            NotImplementedError,
            backend.has_perm,
            factory.make_admin(),
            "not-access",
            factory.make_Node(),
        )

    def test_node_init_user_cannot_access(self):
        backend = MAASAuthorizationBackend()
        self.assertFalse(
            backend.has_perm(
                get_node_init_user(), NodePermission.view, factory.make_Node()
            )
        )

    def test_user_can_view_unowned_node(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(
                factory.make_User(), NodePermission.view, factory.make_Node()
            )
        )

    def test_user_cannot_view_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.view, node))

    def test_user_cannot_view_node_other_pool(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        pool = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool)
        self.rbac_store.allow(user.username, pool, "view")
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.view, node))

    def test_user_can_view_unowned_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.view, node))

    def test_user_can_view_unowned_node_rbac_with_admin(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.view, node))

    def test_user_cannot_view_owned_by_another_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.view, node))

    def test_user_can_view_owned_by_another_node_rbac_view_all(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.rbac_store.allow(user.username, node.pool, "view-all")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.view, node))

    def test_user_can_view_owned_by_another_node_when_admin_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.view, node))

    def test_user_can_view_device_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Device()
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.view, node))

    def test_user_can_edit_node_rbac_admin_machines(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.edit, node))

    def test_user_can_edit_node_rbac_deploy_machines(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "deploy-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.edit, node))

    def test_user_cannot_edit_node_rbac_with_view_or_view_all(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.rbac_store.allow(user.username, node.pool, "view-all")
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.edit, node))

    def test_user_can_edit_owned_node_rbac_with_admin(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.edit, node))

    def test_user_cannot_edit_node_rbac_if_locked(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(locked=True)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machine")
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.edit, node))

    def test_user_cannot_edit_device_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Device()
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.edit, node))

    def test_admin_can_view_nodes_owned_by_others(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(
                factory.make_admin(),
                NodePermission.view,
                make_allocated_node(),
            )
        )

    def test_admin_can_edit_nodes_owned_by_others(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(
                factory.make_admin(),
                NodePermission.edit,
                make_allocated_node(),
            )
        )

    def test_admin_can_admin_nodes(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(
                factory.make_admin(),
                NodePermission.admin,
                make_allocated_node(),
            )
        )

    def test_admin_cannot_admin_locked_nodes(self):
        backend = MAASAuthorizationBackend()
        node = make_allocated_node()
        node.locked = True
        node.save()
        self.assertFalse(
            backend.has_perm(factory.make_admin(), NodePermission.admin, node)
        )

    def test_user_cannot_admin_all_nodes(self):
        backend = MAASAuthorizationBackend()
        self.assertFalse(
            backend.has_perm(factory.make_User(), NodePermission.admin)
        )

    def test_user_can_admin_all_nodes(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(factory.make_admin(), NodePermission.admin)
        )

    def test_user_can_view_all_nodes(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(factory.make_User(), NodePermission.view)
        )

    def test_user_cannot_view_nodes_owned_by_others(self):
        backend = MAASAuthorizationBackend()
        self.assertFalse(
            backend.has_perm(
                factory.make_User(), NodePermission.view, make_allocated_node()
            )
        )

    def test_user_can_view_locked_node(self):
        backend = MAASAuthorizationBackend()
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner, status=NODE_STATUS.DEPLOYED, locked=True
        )
        self.assertTrue(backend.has_perm(owner, NodePermission.view, node))

    def test_owned_status(self):
        # A non-admin user can access nodes he owns.
        backend = MAASAuthorizationBackend()
        node = make_allocated_node()
        self.assertTrue(
            backend.has_perm(node.owner, NodePermission.view, node)
        )

    def test_user_cannot_edit_nodes_owned_by_others(self):
        backend = MAASAuthorizationBackend()
        self.assertFalse(
            backend.has_perm(
                factory.make_User(), NodePermission.edit, make_allocated_node()
            )
        )

    def test_user_can_edit_unowned_node(self):
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(
                factory.make_User(), NodePermission.edit, factory.make_Node()
            )
        )

    def test_user_can_edit_his_own_nodes(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertTrue(
            backend.has_perm(
                user, NodePermission.edit, make_allocated_node(owner=user)
            )
        )

    def test_user_cannot_edit_locked_node(self):
        backend = MAASAuthorizationBackend()
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner, status=NODE_STATUS.DEPLOYED, locked=True
        )
        self.assertFalse(backend.has_perm(owner, NodePermission.edit, node))

    def test_user_can_lock_locked_node(self):
        backend = MAASAuthorizationBackend()
        owner = factory.make_User()
        node = factory.make_Node(
            owner=owner, status=NODE_STATUS.DEPLOYED, locked=True
        )
        self.assertTrue(backend.has_perm(owner, NodePermission.lock, node))

    def test_user_can_lock_owned_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.rbac_store.allow(user.username, node.pool, "deploy-machines")
        self.assertTrue(backend.has_perm(user, NodePermission.lock, node))

    def test_user_cannot_lock_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.assertFalse(backend.has_perm(user, NodePermission.lock, node))

    def test_user_can_lock_node_rbac_owner_other_user(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        self.assertTrue(backend.has_perm(user, NodePermission.lock, node))

    def test_user_cannot_lock_node_rbac_owner_other_user(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.assertFalse(backend.has_perm(user, NodePermission.lock, node))

    def test_user_has_no_admin_permission_on_node(self):
        # NodePermission.admin permission on nodes is granted to super users
        # only.
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(user, NodePermission.admin, factory.make_Node())
        )

    def test_user_has_admin_permission_on_node_with_rbac(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        self.assertTrue(backend.has_perm(user, NodePermission.admin, node))

    def test_admin_doesnt_have_admin_permission_on_node_with_rbac(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        user = factory.make_admin()
        node = factory.make_Node()
        self.assertFalse(backend.has_perm(user, NodePermission.admin, node))

    def test_user_cannot_view_BlockDevice_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        device = factory.make_BlockDevice(node=node)
        self.assertFalse(backend.has_perm(user, NodePermission.view, device))

    def test_user_can_view_BlockDevice_when_no_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.assertTrue(backend.has_perm(user, NodePermission.view, device))

    def test_user_can_view_BlockDevice_when_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        device = factory.make_BlockDevice(node=node)
        self.assertTrue(backend.has_perm(user, NodePermission.view, device))

    def test_user_cannot_view_BlockDevice_when_no_owner_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.view, device))

    def test_user_can_view_BlockDevice_on_unowned_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.view, device))

    def test_user_can_view_BlockDevice_on_other_owned_node_admin_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        device = factory.make_BlockDevice(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.view, device))

    def test_user_cannot_edit_BlockDevice_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        device = factory.make_BlockDevice(node=node)
        self.assertFalse(backend.has_perm(user, NodePermission.edit, device))

    def test_user_can_edit_VirtualBlockDevice_when_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        device = factory.make_VirtualBlockDevice(node=node)
        self.assertTrue(backend.has_perm(user, NodePermission.edit, device))

    def test_user_can_edit_BlockDevice_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.edit, device))

    def test_user_cannot_edit_BlockDevice_rbac_vith_view(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.edit, device))

    def test_user_can_edit_owned_BlockDevice_rbac_with_admin(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        device = factory.make_BlockDevice(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.edit, device))

    def test_user_cannot_edit_BlockDevice_rbac_if_locked(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(locked=True)
        device = factory.make_BlockDevice(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machine")
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.edit, device))

    def test_user_has_no_admin_permission_on_BlockDevice(self):
        # NodePermission.admin permission on block devices is granted to super
        # user only.
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NodePermission.admin, factory.make_BlockDevice()
            )
        )

    def test_user_can_lock_owned_BlockDevice_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        device = factory.make_BlockDevice(node=node)
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.rbac_store.allow(user.username, node.pool, "deploy-machines")
        self.assertTrue(backend.has_perm(user, NodePermission.lock, device))

    def test_user_cannot_lock_BlockDevice_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.assertFalse(backend.has_perm(user, NodePermission.lock, device))

    def test_user_can_lock_BlockDevice_node_rbac_owner_other_user(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        device = factory.make_BlockDevice(node=node)
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        self.assertTrue(backend.has_perm(user, NodePermission.lock, device))

    def test_user_cannot_lock_BlockDevice_node_rbac_owner_other_user(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        device = factory.make_BlockDevice(node=node)
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.assertFalse(backend.has_perm(user, NodePermission.lock, device))

    def test_user_has_admin_permission_on_BlockDevice_with_rbac(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        self.assertTrue(backend.has_perm(user, NodePermission.admin, device))

    def test_admin_doesnt_have_admin_permission_on_BlockDevice_with_rbac(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        user = factory.make_admin()
        node = factory.make_Node()
        device = factory.make_BlockDevice(node=node)
        self.assertFalse(backend.has_perm(user, NodePermission.admin, device))

    def test_user_cannot_view_FilesystemGroup_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.assertFalse(
            backend.has_perm(user, NodePermission.view, filesystem_group)
        )

    def test_user_can_view_FilesystemGroup_when_no_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.assertTrue(
            backend.has_perm(user, NodePermission.view, filesystem_group)
        )

    def test_user_can_view_FilesystemGroup_when_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.assertTrue(
            backend.has_perm(user, NodePermission.view, filesystem_group)
        )

    def test_user_cannot_view_FilesystemGroup_when_no_owner_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(node=node)
        backend = MAASAuthorizationBackend()
        self.assertFalse(
            backend.has_perm(user, NodePermission.view, filesystem_group)
        )

    def test_user_can_view_FilesystemGroup_on_unowned_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(user, NodePermission.view, filesystem_group)
        )

    def test_user_can_view_FilesystemGroup_other_owned_node_admin_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(user, NodePermission.view, filesystem_group)
        )

    def test_user_cannot_edit_FilesystemGroup_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.assertFalse(
            backend.has_perm(user, NodePermission.edit, filesystem_group)
        )

    def test_user_can_edit_FilesystemGroup_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(user, NodePermission.edit, filesystem_group)
        )

    def test_user_cannot_edit_FilesystemGroup_rbac_vith_view(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        backend = MAASAuthorizationBackend()
        self.assertFalse(
            backend.has_perm(user, NodePermission.edit, filesystem_group)
        )

    def test_user_can_edit_owned_FilesystemGroup_rbac_with_admin(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(
            backend.has_perm(user, NodePermission.edit, filesystem_group)
        )

    def test_user_cannot_edit_FilesystemGroup_rbac_if_locked(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(locked=True)
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machine")
        backend = MAASAuthorizationBackend()
        self.assertFalse(
            backend.has_perm(user, NodePermission.edit, filesystem_group)
        )

    def test_user_has_no_admin_permission_on_FilesystemGroup(self):
        # NodePermission.admin permission on block devices is granted to super
        # user only.
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NodePermission.admin, factory.make_FilesystemGroup()
            )
        )

    def test_user_can_lock_owned_FilesystemGroup_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        filesystem_group = factory.make_FilesystemGroup(node=node)
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.rbac_store.allow(user.username, node.pool, "deploy-machines")
        self.assertTrue(
            backend.has_perm(user, NodePermission.lock, filesystem_group)
        )

    def test_user_cannot_lock_FilesystemGroup_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(node=node)
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.assertFalse(
            backend.has_perm(user, NodePermission.lock, filesystem_group)
        )

    def test_user_can_lock_FilesystemGroup_node_rbac_owner_other_user(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(node=node)
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        self.assertTrue(
            backend.has_perm(user, NodePermission.lock, filesystem_group)
        )

    def test_user_cannot_lock_FilesystemGroup_node_rbac_owner_other_user(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(node=node)
        backend = MAASAuthorizationBackend()
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.assertFalse(
            backend.has_perm(user, NodePermission.lock, filesystem_group)
        )

    def test_user_has_admin_permission_on_FilesystemGroup_with_rbac(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        self.assertTrue(
            backend.has_perm(user, NodePermission.admin, filesystem_group)
        )

    def test_admin_no_admin_permission_on_FilesystemGroup_with_rbac(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        user = factory.make_admin()
        node = factory.make_Node()
        filesystem_group = factory.make_FilesystemGroup(node=node)
        self.assertFalse(
            backend.has_perm(user, NodePermission.admin, filesystem_group)
        )

    def test_authenticate_username_password(self):
        password = factory.make_string()
        user = factory.make_User(password=password)
        backend = MAASAuthorizationBackend()
        request = factory.make_fake_request("/")
        ExternalAuthInfoMiddleware(lambda request: request)(request)
        self.assertEqual(
            backend.authenticate(
                request, username=user.username, password=password
            ),
            user,
        )

    def test_authenticate_username_password_external_auth(self):
        SecretManager().set_composite_secret(
            "external-auth", {"url": "https://example.com"}
        )
        password = factory.make_string()
        user = factory.make_User(password=password)
        backend = MAASAuthorizationBackend()
        request = factory.make_fake_request("/")
        ExternalAuthInfoMiddleware(lambda request: request)(request)
        self.assertIsNone(
            backend.authenticate(
                request, username=user.username, password=password
            )
        )

    def test_authenticate_external_user_denied(self):
        password = factory.make_string()
        user = factory.make_User(password=password, is_local=False)
        backend = MAASAuthorizationBackend()
        request = factory.make_fake_request("/")
        self.assertIsNone(
            backend.authenticate(
                request, username=user.username, password=password
            )
        )


class TestMAASAuthorizationBackendInterface(
    MAASServerTestCase, EnableRBACMixin
):
    def test_unowned_interface_requires_admin(self):
        backend = MAASAuthorizationBackend()
        interface = factory.make_Interface(INTERFACE_TYPE.UNKNOWN)
        admin = factory.make_admin()
        user = factory.make_User()
        for perm in [
            NodePermission.view,
            NodePermission.edit,
            NodePermission.admin,
        ]:
            self.assertTrue(backend.has_perm(admin, perm, interface))
            self.assertFalse(backend.has_perm(user, perm, interface))

    def test_user_cannot_view_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        nic = factory.make_Interface(node=node)
        self.assertFalse(backend.has_perm(user, NodePermission.view, nic))

    def test_user_can_view_when_no_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node()
        nic = factory.make_Interface(node=node)
        self.assertTrue(backend.has_perm(user, NodePermission.view, nic))

    def test_user_can_view_when_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        nic = factory.make_Interface(node=node)
        self.assertTrue(backend.has_perm(user, NodePermission.view, nic))

    def test_user_cannot_view_when_no_owner_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        nic = factory.make_Interface(node=node)
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.view, nic))

    def test_user_can_view_on_unowned_node_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        nic = factory.make_Interface(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.view, nic))

    def test_user_can_view_on_other_owned_node_admin_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        nic = factory.make_Interface(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.view, nic))

    def test_user_cannot_edit_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        nic = factory.make_Interface(node=node)
        self.assertFalse(backend.has_perm(user, NodePermission.edit, nic))

    def test_user_can_edit_rbac(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        nic = factory.make_Interface(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.edit, nic))

    def test_user_cannot_edit_rbac_vith_view(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node()
        nic = factory.make_Interface(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.edit, nic))

    def test_owner_cannot_edit_rbac_vith_view(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        nic = factory.make_Interface(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "view")
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.edit, nic))

    def test_user_can_edit_owned_rbac_with_admin(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        nic = factory.make_Interface(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        backend = MAASAuthorizationBackend()
        self.assertTrue(backend.has_perm(user, NodePermission.edit, nic))

    def test_user_cannot_edit_rbac_if_locked(self):
        self.enable_rbac()
        user = factory.make_User()
        node = factory.make_Node(locked=True)
        nic = factory.make_Interface(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machine")
        backend = MAASAuthorizationBackend()
        self.assertFalse(backend.has_perm(user, NodePermission.edit, nic))

    def test_user_has_no_admin_permission(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NodePermission.admin, factory.make_Interface()
            )
        )

    def test_user_has_admin_permission_with_rbac(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node()
        nic = factory.make_Interface(node=node)
        self.rbac_store.add_pool(node.pool)
        self.rbac_store.allow(user.username, node.pool, "admin-machines")
        self.assertTrue(backend.has_perm(user, NodePermission.admin, nic))

    def test_admin_doesnt_have_admin_permission_with_rbac(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        user = factory.make_admin()
        node = factory.make_Node()
        nic = factory.make_Interface(node=node)
        self.assertFalse(backend.has_perm(user, NodePermission.admin, nic))

    def test_owner_can_edit_device_interface(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        parent = factory.make_Node()
        device = factory.make_Device(owner=user, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        self.assertTrue(backend.has_perm(user, NodePermission.edit, interface))

    def test_non_owner_cannot_edit_device_interface(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        owner = factory.make_User()
        parent = factory.make_Node()
        device = factory.make_Device(owner=owner, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        self.assertFalse(
            backend.has_perm(user, NodePermission.edit, interface)
        )

    def test_admin_can_view_device_interface(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        parent = factory.make_Node()
        device = factory.make_Device(owner=user, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        self.assertTrue(
            backend.has_perm(
                factory.make_admin(), NodePermission.view, interface
            )
        )

    def test_admin_can_edit_device_interface(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        parent = factory.make_Node()
        device = factory.make_Device(owner=user, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        self.assertTrue(
            backend.has_perm(
                factory.make_admin(), NodePermission.edit, interface
            )
        )

    def test_admin_can_admin_device_interface(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        parent = factory.make_Node()
        device = factory.make_Device(owner=user, parent=parent)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device
        )
        self.assertTrue(
            backend.has_perm(
                factory.make_admin(), NodePermission.admin, interface
            )
        )


class TestMAASAuthorizationBackendForUnrestrictedRead(MAASServerTestCase):
    scenarios = (
        ("dnsdata", {"factory": factory.make_DNSData}),
        ("dnsresource", {"factory": factory.make_DNSResource}),
        ("domain", {"factory": factory.make_Domain}),
        ("fabric", {"factory": factory.make_Fabric}),
        (
            "interface",
            {
                "factory": partial(
                    factory.make_Interface, INTERFACE_TYPE.PHYSICAL
                )
            },
        ),
        ("subnet", {"factory": factory.make_Subnet}),
        ("space", {"factory": factory.make_Space}),
        ("staticroute", {"factory": factory.make_StaticRoute}),
        ("vlan", {"factory": factory.make_VLAN}),
    )

    def test_user_can_view(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertTrue(
            backend.has_perm(user, NodePermission.view, self.factory())
        )

    def test_user_cannot_edit(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(user, NodePermission.edit, self.factory())
        )

    def test_user_not_admin(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(user, NodePermission.admin, self.factory())
        )

    def test_admin_can_view(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(admin, NodePermission.view, self.factory())
        )

    def test_admin_can_edit(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(admin, NodePermission.edit, self.factory())
        )

    def test_admin_is_admin(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(admin, NodePermission.admin, self.factory())
        )


class TestMAASAuthorizationBackendForAdminRestricted(MAASServerTestCase):
    scenarios = (("discovery", {"factory": factory.make_Discovery}),)

    def test_user_cannot_view(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(user, NodePermission.view, self.factory())
        )

    def test_user_cannot_edit(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(user, NodePermission.edit, self.factory())
        )

    def test_user_not_admin(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(user, NodePermission.admin, self.factory())
        )

    def test_admin_can_view(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(admin, NodePermission.view, self.factory())
        )

    def test_admin_can_edit(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(admin, NodePermission.edit, self.factory())
        )

    def test_admin_is_admin(self):
        backend = MAASAuthorizationBackend()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(admin, NodePermission.admin, self.factory())
        )


class TestNodeVisibility(MAASServerTestCase):
    def test_admin_sees_all_nodes(self):
        nodes = [make_allocated_node(), factory.make_Node()]
        self.assertCountEqual(
            nodes,
            Node.objects.get_nodes(factory.make_admin(), NodePermission.view),
        )

    def test_user_sees_own_nodes_and_unowned_nodes(self):
        user = factory.make_User()
        own_node = make_allocated_node(owner=user)
        make_allocated_node()
        unowned_node = factory.make_Node()
        self.assertCountEqual(
            [own_node, unowned_node],
            Node.objects.get_nodes(own_node.owner, NodePermission.view),
        )


class TestMAASAuthorizationBackendResourcePool(
    MAASServerTestCase, EnableRBACMixin
):
    def test_ResourcePool_requires_ResourcePoolPermission(self):
        backend = MAASAuthorizationBackend()
        pool = factory.make_ResourcePool()
        user = factory.make_User()
        self.assertRaises(
            TypeError, backend.has_perm, user, NodePermission.view, pool
        )

    def test_create_requires_admin(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        admin = factory.make_admin()
        self.assertFalse(backend.has_perm(user, ResourcePoolPermission.create))
        self.assertTrue(backend.has_perm(admin, ResourcePoolPermission.create))

    def test_create_requires_rbac_edit_all_resources(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        pool = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool)
        user1 = factory.make_User()
        self.rbac_store.allow(user1.username, pool, "edit")
        user2 = factory.make_User()
        self.rbac_store.allow(user2.username, ALL_RESOURCES, "edit")
        self.assertFalse(
            backend.has_perm(user1, ResourcePoolPermission.create)
        )
        self.assertTrue(backend.has_perm(user2, ResourcePoolPermission.create))

    def test_view_requires_obj(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertRaises(
            ValueError, backend.has_perm, user, ResourcePoolPermission.view
        )

    def test_edit_requires_obj(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertRaises(
            ValueError, backend.has_perm, user, ResourcePoolPermission.edit
        )

    def test_view_always_viewable(self):
        backend = MAASAuthorizationBackend()
        pool = factory.make_ResourcePool()
        user = factory.make_User()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(user, ResourcePoolPermission.view, pool)
        )
        self.assertTrue(
            backend.has_perm(admin, ResourcePoolPermission.view, pool)
        )

    def test_view_rbac_viewable(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool1)
        self.rbac_store.add_pool(pool2)
        user = factory.make_User()
        self.rbac_store.allow(user.username, pool2, "view")
        self.assertFalse(
            backend.has_perm(user, ResourcePoolPermission.view, pool1)
        )
        self.assertTrue(
            backend.has_perm(user, ResourcePoolPermission.view, pool2)
        )

    def test_edit_requires_admin(self):
        backend = MAASAuthorizationBackend()
        pool = factory.make_ResourcePool()
        user = factory.make_User()
        admin = factory.make_admin()
        self.assertFalse(
            backend.has_perm(user, ResourcePoolPermission.edit, pool)
        )
        self.assertTrue(
            backend.has_perm(admin, ResourcePoolPermission.edit, pool)
        )

    def test_edit_rbac_editable(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        pool1 = factory.make_ResourcePool()
        pool2 = factory.make_ResourcePool()
        self.rbac_store.add_pool(pool1)
        self.rbac_store.add_pool(pool2)
        user = factory.make_User()
        self.rbac_store.allow(user.username, pool1, "view")
        self.rbac_store.allow(user.username, pool2, "edit")
        self.assertFalse(
            backend.has_perm(user, ResourcePoolPermission.edit, pool1)
        )
        self.assertTrue(
            backend.has_perm(user, ResourcePoolPermission.edit, pool2)
        )


class TestMAASAuthorizationBackendPod(MAASServerTestCase, EnableRBACMixin):
    def test_Pod_requires_PodPermission(self):
        backend = MAASAuthorizationBackend()
        pod = factory.make_Pod()
        user = factory.make_User()
        self.assertRaises(
            TypeError, backend.has_perm, user, NodePermission.view, pod
        )

    def test_create_requires_admin(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        admin = factory.make_admin()
        self.assertFalse(backend.has_perm(user, PodPermission.create))
        self.assertTrue(backend.has_perm(admin, PodPermission.create))

    def test_view_requires_obj(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertRaises(
            ValueError, backend.has_perm, user, PodPermission.view
        )

    def test_edit_requires_obj(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertRaises(
            ValueError, backend.has_perm, user, PodPermission.edit
        )

    def test_compose_requires_obj(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertRaises(
            ValueError, backend.has_perm, user, PodPermission.compose
        )

    def test_dynamic_compose_requires_obj(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertRaises(
            ValueError, backend.has_perm, user, PodPermission.dynamic_compose
        )

    def test_view_always_viewable(self):
        backend = MAASAuthorizationBackend()
        pool = factory.make_ResourcePool()
        pod = factory.make_Pod(pool=pool)
        user = factory.make_User()
        admin = factory.make_admin()
        self.assertTrue(backend.has_perm(user, PodPermission.view, pod))
        self.assertTrue(backend.has_perm(admin, PodPermission.view, pod))

    def test_view_rbac_viewable(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        pool1 = factory.make_ResourcePool()
        pod1 = factory.make_Pod(pool=pool1)
        pool2 = factory.make_ResourcePool()
        pod2 = factory.make_Pod(pool=pool2)
        pool3 = factory.make_ResourcePool()
        pod3 = factory.make_Pod(pool=pool3)
        self.rbac_store.add_pool(pool1)
        self.rbac_store.add_pool(pool2)
        self.rbac_store.add_pool(pool3)
        user = factory.make_User()
        self.rbac_store.allow(user.username, pool2, "view")
        self.rbac_store.allow(user.username, pool3, "view-all")
        self.assertFalse(backend.has_perm(user, PodPermission.view, pod1))
        self.assertTrue(backend.has_perm(user, PodPermission.view, pod2))
        self.assertTrue(backend.has_perm(user, PodPermission.view, pod3))

    def test_edit_requires_admin(self):
        backend = MAASAuthorizationBackend()
        pod = factory.make_Pod()
        user = factory.make_User()
        admin = factory.make_admin()
        self.assertFalse(backend.has_perm(user, PodPermission.edit, pod))
        self.assertTrue(backend.has_perm(admin, PodPermission.edit, pod))

    def test_edit_rbac_admin(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        pool1 = factory.make_ResourcePool()
        pod1 = factory.make_Pod(pool=pool1)
        pool2 = factory.make_ResourcePool()
        pod2 = factory.make_Pod(pool=pool2)
        self.rbac_store.add_pool(pool1)
        self.rbac_store.add_pool(pool2)
        user = factory.make_User()
        self.rbac_store.allow(user.username, pool1, "view")
        self.rbac_store.allow(user.username, pool2, "admin-machines")
        self.assertFalse(backend.has_perm(user, PodPermission.edit, pod1))
        self.assertTrue(backend.has_perm(user, PodPermission.edit, pod2))

    def test_compose_requires_admin(self):
        backend = MAASAuthorizationBackend()
        pod = factory.make_Pod()
        user = factory.make_User()
        admin = factory.make_admin()
        self.assertFalse(backend.has_perm(user, PodPermission.compose, pod))
        self.assertTrue(backend.has_perm(admin, PodPermission.compose, pod))

    def test_compose_rbac_admin(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        pool1 = factory.make_ResourcePool()
        pod1 = factory.make_Pod(pool=pool1)
        pool2 = factory.make_ResourcePool()
        pod2 = factory.make_Pod(pool=pool2)
        self.rbac_store.add_pool(pool1)
        self.rbac_store.add_pool(pool2)
        user = factory.make_User()
        self.rbac_store.allow(user.username, pool1, "view")
        self.rbac_store.allow(user.username, pool2, "admin-machines")
        self.assertFalse(backend.has_perm(user, PodPermission.compose, pod1))
        self.assertTrue(backend.has_perm(user, PodPermission.compose, pod2))

    def test_dynamic_compose_doesnt_require_admin(self):
        backend = MAASAuthorizationBackend()
        pod = factory.make_Pod()
        user = factory.make_User()
        admin = factory.make_admin()
        self.assertTrue(
            backend.has_perm(user, PodPermission.dynamic_compose, pod)
        )
        self.assertTrue(
            backend.has_perm(admin, PodPermission.dynamic_compose, pod)
        )

    def test_dynamic_compose_rbac_deploy_admin(self):
        self.enable_rbac()
        backend = MAASAuthorizationBackend()
        pool1 = factory.make_ResourcePool()
        pod1 = factory.make_Pod(pool=pool1)
        pool2 = factory.make_ResourcePool()
        pod2 = factory.make_Pod(pool=pool2)
        pool3 = factory.make_ResourcePool()
        pod3 = factory.make_Pod(pool=pool3)
        self.rbac_store.add_pool(pool1)
        self.rbac_store.add_pool(pool2)
        self.rbac_store.add_pool(pool3)
        user = factory.make_User()
        self.rbac_store.allow(user.username, pool1, "view")
        self.rbac_store.allow(user.username, pool2, "deploy-machines")
        self.rbac_store.allow(user.username, pool3, "admin-machines")
        self.assertFalse(
            backend.has_perm(user, PodPermission.dynamic_compose, pod1)
        )
        self.assertTrue(
            backend.has_perm(user, PodPermission.dynamic_compose, pod2)
        )
        self.assertTrue(
            backend.has_perm(user, PodPermission.dynamic_compose, pod3)
        )
