# Copyright 2016-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.iprange`"""

from maasserver.auth.tests.test_auth import OpenFGAMockMixin
from maasserver.models.iprange import IPRange
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.iprange import IPRangeHandler


class TestIPRangeHandler(MAASServerTestCase):
    def dehydrate_iprange(self, iprange, for_list=False):
        data = {
            "id": iprange.id,
            "created": dehydrate_datetime(iprange.created),
            "updated": dehydrate_datetime(iprange.updated),
            "subnet": iprange.subnet_id,
            "start_ip": iprange.start_ip,
            "end_ip": iprange.end_ip,
            "comment": iprange.comment,
            "user": iprange.user.username if iprange.user else "",
            "type": iprange.type,
            "vlan": iprange.subnet.vlan_id if iprange.subnet else None,
        }
        return data

    def test_get(self):
        user = factory.make_User()
        handler = IPRangeHandler(user, {}, None)
        subnet = factory.make_ipv4_Subnet_with_IPRanges()
        iprange = subnet.iprange_set.first()
        self.assertEqual(
            self.dehydrate_iprange(iprange), handler.get({"id": iprange.id})
        )

    def test_list(self):
        user = factory.make_User()
        handler = IPRangeHandler(user, {}, None)
        factory.make_ipv4_Subnet_with_IPRanges()
        expected_ipranges = [
            self.dehydrate_iprange(iprange, for_list=True)
            for iprange in IPRange.objects.all()
        ]
        self.assertCountEqual(expected_ipranges, handler.list({}))

    def test_create(self):
        user = factory.make_admin()
        factory.make_Subnet(cidr="192.168.0.0/24")
        handler = IPRangeHandler(user, {}, None)
        ip_range = handler.create(
            {
                "type": "reserved",
                "start_ip": "192.168.0.10",
                "end_ip": "192.168.0.20",
            }
        )
        created = IPRange.objects.get(id=ip_range["id"])
        self.assertEqual(created.type, "reserved")
        self.assertEqual(created.start_ip, "192.168.0.10")
        self.assertEqual(created.end_ip, "192.168.0.20")

    def test_update(self):
        user = factory.make_admin()
        factory.make_Subnet(cidr="192.168.0.0/24")
        handler = IPRangeHandler(user, {}, None)
        ip_range = handler.create(
            {
                "type": "reserved",
                "start_ip": "192.168.0.10",
                "end_ip": "192.168.0.20",
            }
        )
        ip_range["end_ip"] = "192.168.0.30"
        handler.update(ip_range)
        created = IPRange.objects.get(id=ip_range["id"])
        self.assertEqual(created.type, "reserved")
        self.assertEqual(created.start_ip, "192.168.0.10")
        self.assertEqual(created.end_ip, "192.168.0.30")

    def test_delete(self):
        user = factory.make_admin()
        factory.make_Subnet(cidr="192.168.0.0/24")
        handler = IPRangeHandler(user, {}, None)
        ip_range = handler.create(
            {
                "type": "reserved",
                "start_ip": "192.168.0.10",
                "end_ip": "192.168.0.20",
            }
        )
        handler.delete(ip_range)
        self.assertIsNone(get_one(IPRange.objects.filter(id=ip_range["id"])))


class TestIPRangeHandlerOpenFGAIntegration(
    OpenFGAMockMixin, MAASServerTestCase
):
    def test_list_requires_can_view_global_entities(self):
        self.openfga_client.can_view_global_entities.return_value = False
        user = factory.make_User()
        factory.make_IPRange()
        handler = IPRangeHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.list, {})

    def test_get_requires_can_view_global_entities(self):
        self.openfga_client.can_view_global_entities.return_value = False
        user = factory.make_User()
        ip_range = factory.make_IPRange()
        handler = IPRangeHandler(user, {}, None)
        self.assertRaises(
            HandlerPermissionError, handler.get, {"id": ip_range.id}
        )

    def test_create_requires_can_edit_global_entities(self):
        self.openfga_client.can_edit_global_entities.return_value = False
        user = factory.make_User()
        handler = IPRangeHandler(user, {}, None)
        self.assertRaises(HandlerPermissionError, handler.create, {})

    def test_update_requires_can_edit_global_entities(self):
        self.openfga_client.can_edit_global_entities.return_value = False
        user = factory.make_User()
        ip_range = factory.make_IPRange()
        handler = IPRangeHandler(user, {}, None)
        self.assertRaises(
            HandlerPermissionError, handler.update, {"id": ip_range.id}
        )

    def test_delete_requires_can_edit_global_entities(self):
        self.openfga_client.can_edit_global_entities.return_value = False
        user = factory.make_User()
        ip_range = factory.make_IPRange()
        handler = IPRangeHandler(user, {}, None)
        self.assertRaises(
            HandlerPermissionError, handler.delete, {"id": ip_range.id}
        )
