# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.fabric`"""

from maasserver.models.fabric import Fabric
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.fabric import FabricHandler
from maastesting.djangotestcase import count_queries


class TestFabricHandler(MAASServerTestCase):
    def dehydrate_fabric(self, fabric):
        data = {
            "id": fabric.id,
            "name": fabric.get_name(),
            "description": fabric.description,
            "class_type": fabric.class_type,
            "updated": dehydrate_datetime(fabric.updated),
            "created": dehydrate_datetime(fabric.created),
            "vlan_ids": sorted(vlan.id for vlan in fabric.vlan_set.all()),
        }
        data["default_vlan_id"] = data["vlan_ids"][0]
        return data

    def test_get(self):
        user = factory.make_User()
        handler = FabricHandler(user, {}, None)
        fabric = factory.make_Fabric()
        vlan = fabric.get_default_vlan()
        for _ in range(3):
            node = factory.make_Node(interface=True)
            interface = node.get_boot_interface()
            interface.vlan = vlan
            interface.save()
        self.assertEqual(
            self.dehydrate_fabric(fabric), handler.get({"id": fabric.id})
        )

    def test_get_default_vlan_is_first(self):
        user = factory.make_User()
        handler = FabricHandler(user, {}, None)
        fabric = factory.make_Fabric()
        default_vlan = fabric.get_default_vlan()
        tagged_vlan_ids = [
            factory.make_VLAN(fabric=fabric).id for _ in range(3)
        ]
        observed = handler.get({"id": fabric.id})
        self.assertEqual(
            [default_vlan.id] + tagged_vlan_ids, observed["vlan_ids"]
        )

    def test_list(self):
        user = factory.make_User()
        handler = FabricHandler(user, {}, None)
        factory.make_Fabric()
        expected_fabrics = [
            self.dehydrate_fabric(fabric) for fabric in Fabric.objects.all()
        ]
        self.assertCountEqual(expected_fabrics, handler.list({}))

    def test_list_constant_queries(self):
        user = factory.make_User()
        handler = FabricHandler(user, {}, None)
        for _ in range(10):
            fabric = factory.make_Fabric()
            vlan = fabric.get_default_vlan()
            for _ in range(3):
                node = factory.make_Node(interface=True)
                interface = node.get_boot_interface()
                interface.vlan = vlan
                interface.save()

        queries_one, _ = count_queries(handler.list, {"limit": 1})
        queries_multiple, _ = count_queries(handler.list, {})

        self.assertEqual(queries_one, queries_multiple)
