# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.vlan`"""

__all__ = []

from maasserver.models.vlan import VLAN
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.handlers.timestampedmodel import dehydrate_datetime
from maasserver.websockets.handlers.vlan import VLANHandler


class TestVLANHandler(MAASServerTestCase):

    def dehydrate_vlan(self, vlan, for_list=False):
        data = {
            "id": vlan.id,
            "name": vlan.name,
            "vid": vlan.vid,
            "mtu": vlan.mtu,
            "fabric": vlan.fabric_id,
            "updated": dehydrate_datetime(vlan.updated),
            "created": dehydrate_datetime(vlan.created),
            "dhcp_on": vlan.dhcp_on,
            "primary_rack": vlan.primary_rack,
            "secondary_rack": vlan.secondary_rack,
            "subnet_ids": sorted([
                subnet.id
                for subnet in vlan.subnet_set.all()
            ]),
            "nodes_count": len({
                interface.node_id
                for interface in vlan.interface_set.all()
                if interface.node_id is not None
            }),
        }
        if not for_list:
            data['node_ids'] = sorted(list({
                interface.node_id
                for interface in vlan.interface_set.all()
                if interface.node_id is not None
            }))
            data['space_ids'] = sorted([
                subnet.space.id
                for subnet in vlan.subnet_set.all()
                ])
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
        self.assertEqual(
            self.dehydrate_vlan(vlan),
            handler.get({"id": vlan.id}))

    def test_list(self):
        user = factory.make_User()
        handler = VLANHandler(user, {})
        factory.make_VLAN()
        expected_vlans = [
            self.dehydrate_vlan(vlan, for_list=True)
            for vlan in VLAN.objects.all()
            ]
        self.assertItemsEqual(
            expected_vlans,
            handler.list({}))
