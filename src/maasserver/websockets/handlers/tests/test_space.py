# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.space`"""

__all__ = []

from maasserver.models.space import Space
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.space import SpaceHandler
from testtools import ExpectedException
from testtools.matchers import Equals


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
        self.assertItemsEqual(expected_spaces, handler.list({}))


class TestSpaceHandlerDelete(MAASServerTestCase):
    def test__delete_as_admin_success(self):
        user = factory.make_admin()
        handler = SpaceHandler(user, {}, None)
        space = factory.make_Space()
        handler.delete({"id": space.id})
        space = reload_object(space)
        self.assertThat(space, Equals(None))

    def test__delete_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = SpaceHandler(user, {}, None)
        space = factory.make_Space()
        with ExpectedException(AssertionError, "Permission denied."):
            handler.delete({"id": space.id})

    def test__reloads_user(self):
        user = factory.make_admin()
        handler = SpaceHandler(user, {}, None)
        space = factory.make_Space()
        user.is_superuser = False
        user.save()
        with ExpectedException(AssertionError, "Permission denied."):
            handler.delete({"id": space.id})
