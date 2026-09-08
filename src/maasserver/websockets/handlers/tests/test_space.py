# Copyright 2015-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.space`"""

from unittest.mock import MagicMock

from maasserver import openfga
from maasserver.models.space import Space
from maasserver.rbac import rbac
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.space import SpaceHandler
from maastesting.djangotestcase import count_queries


class TestSpaceHandler(MAASServerTestCase):
    def dehydrate_space(self, space):
        data = {
            "id": space.id,
            "name": space.get_name(),
            "description": space.description,
            "updated": dehydrate_datetime(space.updated),
            "created": dehydrate_datetime(space.created),
            "subnet_ids": sorted(
                subnet.id for subnet in space.subnet_set.all()
            ),
            "vlan_ids": sorted(vlan.id for vlan in space.vlan_set.all()),
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = SpaceHandler(user, {}, None)
        space = factory.make_Space()
        for _ in range(3):
            node = factory.make_Node(interface=True)
            interface = node.get_boot_interface()
            subnet = factory.make_Subnet(space=space, vlan=interface.vlan)
            factory.make_StaticIPAddress(subnet=subnet, interface=interface)
        self.assertEqual(
            self.dehydrate_space(space), handler.get({"id": space.id})
        )

    def test_list(self):
        user = factory.make_User()
        handler = SpaceHandler(user, {}, None)
        factory.make_Space()
        expected_spaces = [
            self.dehydrate_space(space) for space in Space.objects.all()
        ]
        self.assertCountEqual(expected_spaces, handler.list({}))

    def test_list_constant_queries(self):
        user = factory.make_User()
        handler = SpaceHandler(user, {}, None)
        for _ in range(10):
            space = factory.make_Space()
            node = factory.make_Node(interface=True)
            interface = node.get_boot_interface()
            subnet = factory.make_Subnet(space=space, vlan=interface.vlan)
            factory.make_StaticIPAddress(subnet=subnet, interface=interface)

        # Warm the RBAC enabled-state cache: the view-permission check reads
        # it lazily (one DB query), and RBACClearFixture resets it each test.
        # Priming here keeps that one-off query out of the measured section so
        # both counts reflect steady state.
        rbac.is_enabled()

        queries_one, _ = count_queries(handler.list, {"limit": 1})
        queries_multiple, _ = count_queries(handler.list, {})

        self.assertEqual(queries_one, queries_multiple)


class TestSpaceHandlerDelete(MAASServerTestCase):
    def test_delete_as_admin_success(self):
        user = factory.make_admin()
        handler = SpaceHandler(user, {}, None)
        space = factory.make_Space()
        handler.delete({"id": space.id})
        space = reload_object(space)
        self.assertIsNone(space)

    def test_delete_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = SpaceHandler(user, {}, None)
        space = factory.make_Space()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.delete({"id": space.id})

    def test_reloads_user(self):
        user = factory.make_admin()
        handler = SpaceHandler(user, {}, None)
        space = factory.make_Space()
        user.is_superuser = False
        user.save()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.delete({"id": space.id})


class TestSpaceHandlerViewPermission(MAASServerTestCase):
    def deny_global_view(self):
        client = openfga.get_openfga_client()
        client.can_view_global_entities = MagicMock(return_value=False)

    def test_list_requires_view_permission(self):
        self.deny_global_view()
        handler = SpaceHandler(factory.make_User(), {}, None)
        factory.make_Space()
        self.assertRaises(HandlerPermissionError, handler.list, {})

    def test_get_requires_view_permission(self):
        self.deny_global_view()
        space = factory.make_Space()
        handler = SpaceHandler(factory.make_User(), {}, None)
        self.assertRaises(
            HandlerPermissionError, handler.get, {"id": space.id}
        )


class TestSpaceHandlerEditPermission(MAASServerTestCase):
    def deny_global_edit(self):
        client = openfga.get_openfga_client()
        client.can_edit_global_entities = MagicMock(return_value=False)

    def test_create_requires_edit_permission(self):
        self.deny_global_edit()
        handler = SpaceHandler(factory.make_User(), {}, None)
        self.assertRaises(HandlerPermissionError, handler.create, {})

    def test_update_requires_edit_permission(self):
        self.deny_global_edit()
        space = factory.make_Space()
        handler = SpaceHandler(factory.make_User(), {}, None)
        self.assertRaises(
            HandlerPermissionError, handler.update, {"id": space.id}
        )
