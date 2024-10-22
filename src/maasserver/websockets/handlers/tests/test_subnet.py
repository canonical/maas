# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import re
from unittest.mock import sentinel

from fixtures import FakeLogger
from netaddr import IPNetwork

from maasserver.api import discoveries as discoveries_module
from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, NODE_STATUS
from maasserver.models.subnet import Subnet
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.websockets.base import dehydrate_datetime
from maasserver.websockets.handlers.subnet import SubnetHandler
from maastesting.djangotestcase import count_queries
from provisioningserver.utils.network import IPRangeStatistics


class TestSubnetHandler(MAASServerTestCase):
    def dehydrate_subnet(self, subnet, for_list=False):
        data = {
            "id": subnet.id,
            "updated": dehydrate_datetime(subnet.updated),
            "created": dehydrate_datetime(subnet.created),
            "name": subnet.name,
            "description": subnet.description,
            "dns_servers": (
                " ".join(sorted(subnet.dns_servers))
                if subnet.dns_servers is not None
                else ""
            ),
            "vlan": subnet.vlan_id,
            "space": subnet.vlan.space_id,
            "rdns_mode": subnet.rdns_mode,
            "allow_dns": subnet.allow_dns,
            "allow_proxy": subnet.allow_proxy,
            "cidr": subnet.cidr,
            "gateway_ip": subnet.gateway_ip,
            "active_discovery": subnet.active_discovery,
            "managed": subnet.managed,
            "disabled_boot_architectures": subnet.disabled_boot_architectures,
        }
        full_range = subnet.get_iprange_usage()
        metadata = IPRangeStatistics(full_range)
        data["statistics"] = metadata.render_json(
            include_ranges=True, include_suggestions=True
        )
        data["version"] = IPNetwork(subnet.cidr).version
        if not for_list:
            data["ip_addresses"] = subnet.render_json_for_related_ips(
                with_username=True, with_summary=True
            )
        return data

    def test_get(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        expected_data = self.dehydrate_subnet(subnet)
        result = handler.get({"id": subnet.id})
        self.assertEqual(expected_data, result)

    def test_get_handles_null_dns_servers(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        subnet.dns_servers = None
        subnet.save()
        expected_data = self.dehydrate_subnet(subnet)
        result = handler.get({"id": subnet.id})
        self.assertEqual(expected_data, result)

    def test_get_uses_consistent_queries(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        self.assertIsNone(handler.cache.get("staticroutes"))
        queries, _ = count_queries(handler.get, {"id": subnet.id})
        self.assertEqual(5, queries)
        self.assertIsNotNone(handler.cache["staticroutes"])

    def test_list(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {}, None)
        factory.make_Subnet()
        expected_subnets = [
            self.dehydrate_subnet(subnet, for_list=True)
            for subnet in Subnet.objects.all()
        ]
        self.assertCountEqual(expected_subnets, handler.list({}))

    def test_list_uses_consistent_queries(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        factory.make_Interface(iftype=INTERFACE_TYPE.UNKNOWN, subnet=subnet)
        self.assertIsNone(handler.cache.get("staticroutes"))
        queries_one, _ = count_queries(handler.list, {})

        for _ in range(5):
            subnet = factory.make_Subnet()
            for x in range(3):
                node = factory.make_Node_with_Interface_on_Subnet(
                    subnet=subnet, status=NODE_STATUS.READY
                )
                iface = node.current_config.interface_set.first()
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.STICKY,
                    subnet=subnet,
                    interface=iface,
                )

        self.assertIsNotNone(handler.cache["staticroutes"])
        del handler.cache["staticroutes"]
        queries_all, _ = count_queries(handler.list, {})
        self.assertEqual(queries_one, queries_all)
        self.assertIsNotNone(handler.cache["staticroutes"])
        self.assertEqual(4, queries_one)


class TestSubnetHandlerDelete(MAASServerTestCase):
    def test_delete_as_admin_success(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        handler.delete({"id": subnet.id})
        subnet = reload_object(subnet)
        self.assertIsNone(subnet)

    def test_delete_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.delete({"id": subnet.id})

    def test_reloads_user(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        user.is_superuser = False
        user.save()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.delete({"id": subnet.id})


class TestSubnetHandlerCreate(MAASServerTestCase):
    def test_create_as_admin_succeeds(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        vlan = factory.make_VLAN()
        result = handler.create({"vlan": vlan.id, "cidr": "192.168.0.0/24"})
        subnet = Subnet.objects.get(id=result["id"])
        self.assertEqual("192.168.0.0/24", subnet.cidr)

    def test_create_as_admin_succeeds_even_with_a_specified_space(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        vlan = factory.make_VLAN()
        space = factory.make_Space()
        result = handler.create(
            {"vlan": vlan.id, "cidr": "192.168.0.0/24", "space": space.id}
        )
        subnet = Subnet.objects.get(id=result["id"])
        self.assertEqual("192.168.0.0/24", subnet.cidr)

    def test_create_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {}, None)
        vlan = factory.make_VLAN()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.create({"vlan": vlan.id, "cidr": "192.168.0.0/24"})

    def test_create_reloads_user(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        vlan = factory.make_VLAN()
        user.is_superuser = False
        user.save()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.create({"vlan": vlan.id, "cidr": "192.168.0.0/24"})


class TestSubnetHandlerUpdate(MAASServerTestCase):
    def test_update_as_admin_succeeds(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        new_description = "does anyone use this field?"
        handler.update({"id": subnet.id, "description": new_description})
        subnet = reload_object(subnet)
        self.assertEqual(new_description, subnet.description)

    def test_update_as_admin_succeeds_even_with_a_specified_space(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet(description="sad subnet")
        space = factory.make_Space()
        new_description = "happy subnet"
        handler.update(
            {
                "id": subnet.id,
                "space": space.id,
                "description": new_description,
            }
        )
        subnet = reload_object(subnet)
        self.assertEqual(new_description, subnet.description)

    def test_update_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.update({"id": subnet.id})

    def test_reloads_user(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        user.is_superuser = False
        user.save()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.update({"id": subnet.id})


class TestSubnetHandlerScan(MAASServerTestCase):
    def setUp(self):
        self.scan_all_rack_networks = self.patch(
            discoveries_module.scan_all_rack_networks
        )
        self.scan_all_rack_networks.return_value = sentinel.rpc_result
        self.user_friendly_scan_results = self.patch(
            discoveries_module.user_friendly_scan_results
        )
        self.user_friendly_scan_results.return_value = sentinel.result
        return super().setUp()

    def test_scan_as_admin_succeeds_and_returns_user_friendly_result(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet(version=4)
        rack = factory.make_RackController()
        factory.make_Interface(node=rack, subnet=subnet)
        cidr = subnet.get_ipnetwork()
        result = handler.scan({"id": subnet.id})
        self.assertEqual(sentinel.result, result)
        self.scan_all_rack_networks.assert_called_once_with(cidrs=[cidr])
        self.user_friendly_scan_results.assert_called_once_with(
            sentinel.rpc_result
        )

    def test_scan_as_admin_logs_the_fact_that_a_scan_happened(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet(version=4)
        rack = factory.make_RackController()
        factory.make_Interface(node=rack, subnet=subnet)
        logger = self.useFixture(FakeLogger())
        cidr = subnet.get_ipnetwork()
        handler.scan({"id": subnet.id})
        self.assertRegex(
            logger.output,
            "User '%s' initiated a neighbour discovery scan against subnet: %s"
            % (re.escape(user.username), re.escape(str(cidr))),
        )

    def test_scan_ipv6_fails(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet(version=6)
        with self.assertRaisesRegex(ValueError, ".*only IPv4.*"):
            handler.scan({"id": subnet.id})

    def test_scan_fails_if_no_rack_is_configured_with_subnet(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet(version=4)
        with self.assertRaisesRegex(
            ValueError, ".*must be configured on a rack*"
        ):
            handler.scan({"id": subnet.id})

    def test_scan_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.scan({"id": subnet.id})

    def test_reloads_user(self):
        user = factory.make_admin()
        handler = SubnetHandler(user, {}, None)
        subnet = factory.make_Subnet()
        user.is_superuser = False
        user.save()
        with self.assertRaisesRegex(AssertionError, "Permission denied."):
            handler.scan({"id": subnet.id})
