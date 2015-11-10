# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.vlan`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models.vlan import VLAN
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from maasserver.websockets.handlers.vlan import VLANHandler


class TestVLANHandler(MAASServerTestCase):

    def dehydrate_vlan(self, vlan):
        data = {
            "id": vlan.id,
            "name": vlan.get_name(),
            "vid": vlan.vid,
            "mtu": vlan.mtu,
            "fabric": vlan.fabric_id,
            "updated": dehydrate_datetime(vlan.updated),
            "created": dehydrate_datetime(vlan.created),
            "subnet_ids": [
                subnet.id
                for subnet in vlan.subnet_set.all()
            ],
            "nodes_count": len({
                interface.node_id
                for interface in vlan.interface_set.all()
                if interface.node_id is not None
            }),
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = VLANHandler(user, {})
        vlan = factory.make_VLAN()
        for _ in range(3):
            factory.make_Subnet(vlan=vlan)
        for _ in range(3):
            node = factory.make_Node(interface=True)
            interface = node.get_boot_interface()
            interface.vlan = vlan
            interface.save()
        self.assertEquals(
            self.dehydrate_vlan(vlan),
            handler.get({"id": vlan.id}))

    def test_list(self):
        user = factory.make_User()
        handler = VLANHandler(user, {})
        factory.make_VLAN()
        expected_vlans = [
            self.dehydrate_vlan(vlan)
            for vlan in VLAN.objects.all()
            ]
        self.assertItemsEqual(
            expected_vlans,
            handler.list({}))
