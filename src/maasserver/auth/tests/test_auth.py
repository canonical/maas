# Copyright 2012-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from functools import partial
import http.client
from unittest.mock import MagicMock

from django.urls import reverse

from maasserver.auth import MAASAuthorizationBackend
from maasserver.enum import INTERFACE_TYPE, NODE_STATUS
from maasserver.models import Node
from maasserver.permissions import (
    NodePermission,
    PodPermission,
    ResourcePoolPermission,
)
from maasserver.permissions import NodePermission, ResourcePoolPermission
from maasserver.rbac import ALL_RESOURCES, FakeRBACClient, rbac
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import OpenFGAMock
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


class OpenFGAMockMixin:
    """Mixin to disable auto-mocking and set up a custom OpenFGA client mock."""

    auto_mock_openfga = False

    def setUp(self):
        super().setUp()
        self.openfga_client = MagicMock()
        self.useFixture(OpenFGAMock(client=self.openfga_client))


class TestMAASAuthorizationBackend(MAASServerTestCase):
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

    def test_user_has_no_admin_permission_on_node(self):
        # NodePermission.admin permission on nodes is granted to super users
        # only.
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(user, NodePermission.admin, factory.make_Node())
        )

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

    def test_user_cannot_edit_FilesystemGroup_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        filesystem_group = factory.make_FilesystemGroup(node=node)
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


class TestMAASAuthorizationBackendInterface(MAASServerTestCase):
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

    def test_user_cannot_edit_when_not_node_owner(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        nic = factory.make_Interface(node=node)
        self.assertFalse(backend.has_perm(user, NodePermission.edit, nic))

    def test_user_has_no_admin_permission(self):
        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(
                user, NodePermission.admin, factory.make_Interface()
            )
        )

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


class TestMAASAuthorizationBackendForUnrestrictedReadOpenFGAIntegration(
    OpenFGAMockMixin, MAASServerTestCase
):
    scenarios = (
        ("dnsdata", {"factory": factory.make_DNSData}),
        ("dnsresource", {"factory": factory.make_DNSResource}),
        ("domain", {"factory": factory.make_Domain}),
        ("fabric", {"factory": factory.make_Fabric}),
        ("subnet", {"factory": factory.make_Subnet}),
        ("space", {"factory": factory.make_Space}),
        ("staticroute", {"factory": factory.make_StaticRoute}),
        ("vlan", {"factory": factory.make_VLAN}),
    )

    def test_user_can_view(self):
        self.openfga_client.can_view_global_entities.return_value = True

        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertTrue(
            backend.has_perm(user, NodePermission.view, self.factory())
        )
        self.openfga_client.can_view_global_entities.assert_called_once_with(
            user
        )

    def test_user_can_edit(self):
        self.openfga_client.can_edit_global_entities.return_value = True

        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertTrue(
            backend.has_perm(user, NodePermission.edit, self.factory())
        )
        self.openfga_client.can_edit_global_entities.assert_called_once_with(
            user
        )

    def test_user_can_admin(self):
        self.openfga_client.can_edit_global_entities.return_value = True

        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        self.assertTrue(
            backend.has_perm(user, NodePermission.admin, self.factory())
        )
        self.openfga_client.can_edit_global_entities.assert_called_once_with(
            user
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


class TestMAASAuthorizationBackendResourcePool(MAASServerTestCase):
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



class TestMAASAuthorizationBackendResourcePoolOpenFGAIntegration(
    OpenFGAMockMixin, MAASServerTestCase
):
    def test_create_requires_can_edit_machines(self):
        self.openfga_client.can_edit_machines.return_value = False

        backend = MAASAuthorizationBackend()
        user = factory.make_User()

        self.assertFalse(backend.has_perm(user, ResourcePoolPermission.create))
        self.openfga_client.can_edit_machines.assert_called_once_with(user)

    def test_view_always_viewable(self):
        self.openfga_client.can_view_available_machines_in_pool.return_value = False

        backend = MAASAuthorizationBackend()
        pool = factory.make_ResourcePool()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(user, ResourcePoolPermission.view, pool)
        )
        self.openfga_client.can_view_available_machines_in_pool.assert_called_once_with(
            user, pool.id
        )

    def test_edit_requires_can_edit_machines_in_pool(self):
        self.openfga_client.can_edit_machines_in_pool.return_value = False

        backend = MAASAuthorizationBackend()
        pool = factory.make_ResourcePool()
        user = factory.make_User()
        self.assertFalse(
            backend.has_perm(user, ResourcePoolPermission.edit, pool)
        )
        self.openfga_client.can_edit_machines_in_pool.assert_called_once_with(
            user, pool.id
        )


class TestMAASAuthorizationBackendInterfaceOpenFGAIntegration(
    OpenFGAMockMixin, MAASServerTestCase
):
    def test_unowned_interface_requires_admin(self):
        self.openfga_client.can_edit_machines.return_value = True

        backend = MAASAuthorizationBackend()
        interface = factory.make_Interface(INTERFACE_TYPE.UNKNOWN)
        user = factory.make_User()

        for perm in [
            NodePermission.view,
            NodePermission.edit,
            NodePermission.admin,
        ]:
            self.assertTrue(backend.has_perm(user, perm, interface))

    def test_user_can_view_if_can_view_machines(self):
        self.openfga_client.can_view_machines_in_pool.return_value = True

        backend = MAASAuthorizationBackend()
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        nic = factory.make_Interface(node=node)
        self.assertTrue(backend.has_perm(user, NodePermission.view, nic))

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
