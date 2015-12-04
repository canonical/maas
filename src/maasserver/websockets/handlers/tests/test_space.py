# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.space`"""

__all__ = []

from maasserver.models.space import Space
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.space import SpaceHandler
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime


class TestSpaceHandler(MAASServerTestCase):

    def dehydrate_space(self, space):
        data = {
            "id": space.id,
            "name": space.get_name(),
            "updated": dehydrate_datetime(space.updated),
            "created": dehydrate_datetime(space.created),
            "subnet_ids": [
                subnet.id
                for subnet in space.subnet_set.all()
            ],
            "nodes_count": len({
                interface.node_id
                for subnet in space.subnet_set.all()
                for ipaddress in subnet.staticipaddress_set.all()
                for interface in ipaddress.interface_set.all()
                if interface.node_id is not None
            }),
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = SpaceHandler(user, {})
        space = factory.make_Space()
        for _ in range(3):
            node = factory.make_Node(interface=True)
            interface = node.get_boot_interface()
            subnet = factory.make_Subnet(space=space, vlan=interface.vlan)
            factory.make_StaticIPAddress(subnet=subnet, interface=interface)
        self.assertEqual(
            self.dehydrate_space(space),
            handler.get({"id": space.id}))

    def test_list(self):
        user = factory.make_User()
        handler = SpaceHandler(user, {})
        factory.make_Space()
        expected_spaces = [
            self.dehydrate_space(space)
            for space in Space.objects.all()
            ]
        self.assertItemsEqual(
            expected_spaces,
            handler.list({}))
