# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client
import json
import random

from django.conf import settings
from django.http import QueryDict
from django.urls import reverse

from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_STATUS,
    RDNS_MODE,
    RDNS_MODE_CHOICES,
)
from maasserver.testing.api import APITestCase, explain_unexpected_response
from maasserver.testing.factory import factory
from maasserver.utils.orm import reload_object
from maastesting.djangotestcase import CountQueries
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.utils.network import inet_ntop, IPRangeStatistics


def get_subnets_uri():
    """Return a Subnet's URI on the API."""
    return reverse("subnets_handler", args=[])


def get_subnet_uri(subnet):
    """Return a Subnet URI on the API."""
    if isinstance(subnet, str):
        return reverse("subnet_handler", args=[subnet])
    else:
        return reverse("subnet_handler", args=[subnet.id])


class TestSubnetsAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/subnets/", get_subnets_uri())

    def test_read(self):
        def make_subnet():
            space = factory.make_Space()
            subnet = factory.make_Subnet(space=space)
            primary_rack = factory.make_RackController(subnet=subnet)
            secondary_rack = factory.make_RackController(subnet=subnet)
            relay_vlan = factory.make_VLAN()
            vlan = subnet.vlan
            vlan.dhcp_on = True
            vlan.primary_rack = primary_rack
            vlan.secondary_rack = secondary_rack
            vlan.relay_vlan = relay_vlan
            vlan.save()
            return subnet

        subnets = [make_subnet()]
        uri = get_subnets_uri()
        with CountQueries() as counter:
            response = self.client.get(uri)
        base_count = counter.count

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        result_ids = [
            subnet["id"]
            for subnet in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(
            [subnet.id for subnet in subnets],
            result_ids,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET)),
        )

        subnets.append(make_subnet())
        with CountQueries() as counter:
            response = self.client.get(uri)
        # XXX: These should be the same.
        self.assertEqual(base_count + 9, counter.count)
        self.assertEqual((base_count, counter.count), (24, 33))

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        result_ids = [
            subnet["id"]
            for subnet in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual([subnet.id for subnet in subnets], result_ids)

    def test_create(self):
        self.become_admin()
        subnet_name = factory.make_name("subnet")
        vlan = factory.make_VLAN()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        rdns_mode = factory.pick_choice(RDNS_MODE_CHOICES)
        allow_proxy = factory.pick_bool()
        allow_dns = factory.pick_bool()
        gateway_ip = factory.pick_ip_in_network(network)
        managed = factory.pick_bool()
        description = factory.make_string()
        dns_servers = []
        for _ in range(2):
            dns_servers.append(
                factory.pick_ip_in_network(
                    network, but_not=[gateway_ip] + dns_servers
                )
            )
        disabled_arches = random.sample(
            [
                boot_method.name
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet or boot_method.path_prefix_http
            ],
            3,
        )

        uri = get_subnets_uri()
        response = self.client.post(
            uri,
            {
                "name": subnet_name,
                "vlan": vlan.id,
                "cidr": cidr,
                "gateway_ip": gateway_ip,
                "dns_servers": ",".join(dns_servers),
                "rdns_mode": rdns_mode,
                "allow_proxy": allow_proxy,
                "allow_dns": allow_dns,
                "managed": managed,
                "description": description,
                "disabled_boot_architectures": ",".join(disabled_arches),
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        created_subnet = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(subnet_name, created_subnet["name"])
        self.assertEqual(vlan.vid, created_subnet["vlan"]["vid"])
        self.assertEqual(cidr, created_subnet["cidr"])
        self.assertEqual(gateway_ip, created_subnet["gateway_ip"])
        self.assertEqual(dns_servers, created_subnet["dns_servers"])
        self.assertEqual(rdns_mode, created_subnet["rdns_mode"])
        self.assertEqual(allow_proxy, created_subnet["allow_proxy"])
        self.assertEqual(allow_dns, created_subnet["allow_dns"])
        self.assertEqual(managed, created_subnet["managed"])
        self.assertEqual(description, created_subnet["description"])
        self.assertCountEqual(
            disabled_arches,
            created_subnet["disabled_boot_architectures"],
        )

    def test_create_defaults_to_allow_dns(self):
        self.become_admin()
        subnet_name = factory.make_name("subnet")
        vlan = factory.make_VLAN()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        rdns_mode = factory.pick_choice(RDNS_MODE_CHOICES)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = []
        for _ in range(2):
            dns_servers.append(
                factory.pick_ip_in_network(
                    network, but_not=[gateway_ip] + dns_servers
                )
            )
        uri = get_subnets_uri()
        response = self.client.post(
            uri,
            {
                "name": subnet_name,
                "vlan": vlan.id,
                "cidr": cidr,
                "gateway_ip": gateway_ip,
                "dns_servers": ",".join(dns_servers),
                "rdns_mode": rdns_mode,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        created_subnet = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(subnet_name, created_subnet["name"])
        self.assertEqual(vlan.vid, created_subnet["vlan"]["vid"])
        self.assertEqual(cidr, created_subnet["cidr"])
        self.assertEqual(gateway_ip, created_subnet["gateway_ip"])
        self.assertEqual(dns_servers, created_subnet["dns_servers"])
        self.assertEqual(rdns_mode, created_subnet["rdns_mode"])
        self.assertTrue(created_subnet["allow_dns"])

    def test_create_defaults_to_allow_proxy(self):
        self.become_admin()
        subnet_name = factory.make_name("subnet")
        vlan = factory.make_VLAN()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        rdns_mode = factory.pick_choice(RDNS_MODE_CHOICES)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = []
        for _ in range(2):
            dns_servers.append(
                factory.pick_ip_in_network(
                    network, but_not=[gateway_ip] + dns_servers
                )
            )
        uri = get_subnets_uri()
        response = self.client.post(
            uri,
            {
                "name": subnet_name,
                "vlan": vlan.id,
                "cidr": cidr,
                "gateway_ip": gateway_ip,
                "dns_servers": ",".join(dns_servers),
                "rdns_mode": rdns_mode,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        created_subnet = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(subnet_name, created_subnet["name"])
        self.assertEqual(vlan.vid, created_subnet["vlan"]["vid"])
        self.assertEqual(cidr, created_subnet["cidr"])
        self.assertEqual(gateway_ip, created_subnet["gateway_ip"])
        self.assertEqual(dns_servers, created_subnet["dns_servers"])
        self.assertEqual(rdns_mode, created_subnet["rdns_mode"])
        self.assertTrue(created_subnet["allow_proxy"])

    def test_create_defaults_to_managed(self):
        self.become_admin()
        subnet_name = factory.make_name("subnet")
        vlan = factory.make_VLAN()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        rdns_mode = factory.pick_choice(RDNS_MODE_CHOICES)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = []
        for _ in range(2):
            dns_servers.append(
                factory.pick_ip_in_network(
                    network, but_not=[gateway_ip] + dns_servers
                )
            )
        uri = get_subnets_uri()
        response = self.client.post(
            uri,
            {
                "name": subnet_name,
                "vlan": vlan.id,
                "cidr": cidr,
                "gateway_ip": gateway_ip,
                "dns_servers": ",".join(dns_servers),
                "rdns_mode": rdns_mode,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        created_subnet = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(subnet_name, created_subnet["name"])
        self.assertEqual(vlan.vid, created_subnet["vlan"]["vid"])
        self.assertEqual(cidr, created_subnet["cidr"])
        self.assertEqual(gateway_ip, created_subnet["gateway_ip"])
        self.assertEqual(dns_servers, created_subnet["dns_servers"])
        self.assertEqual(rdns_mode, created_subnet["rdns_mode"])
        self.assertTrue(created_subnet["managed"])

    def test_create_admin_only(self):
        subnet_name = factory.make_name("subnet")
        uri = get_subnets_uri()
        response = self.client.post(uri, {"name": subnet_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_requires_cidr(self):
        self.become_admin()
        uri = get_subnets_uri()
        response = self.client.post(uri, {})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            {"cidr": ["This field is required."]},
            json.loads(response.content.decode(settings.DEFAULT_CHARSET)),
        )


class TestSubnetAPI(APITestCase.ForUser):
    def test_handler_path(self):
        subnet = factory.make_Subnet()
        self.assertEqual(
            "/MAAS/api/2.0/subnets/%s/" % subnet.id, get_subnet_uri(subnet)
        )

    def test_read_basic(self):
        subnet = factory.make_Subnet(
            name="my-subnet",
            cidr="10.10.10.0/24",
            gateway_ip=None,
            space=None,
            dns_servers=[],
            disabled_boot_architectures=[],
        )
        uri = get_subnet_uri(subnet)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_subnet = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            parsed_subnet,
            {
                "id": subnet.id,
                "name": "my-subnet",
                "active_discovery": False,
                "allow_dns": True,
                "allow_proxy": True,
                "description": "",
                "space": "undefined",
                "cidr": "10.10.10.0/24",
                "gateway_ip": None,
                "dns_servers": [],
                "managed": True,
                "disabled_boot_architectures": [],
                "rdns_mode": RDNS_MODE.DEFAULT,
                "resource_uri": f"/MAAS/api/2.0/subnets/{subnet.id}/",
                "vlan": {
                    "id": subnet.vlan_id,
                    "dhcp_on": subnet.vlan.dhcp_on,
                    "external_dhcp": subnet.vlan.external_dhcp,
                    "fabric": subnet.vlan.fabric.get_name(),
                    "fabric_id": subnet.vlan.fabric_id,
                    "mtu": subnet.vlan.mtu,
                    "primary_rack": None,
                    "secondary_rack": None,
                    "space": "undefined",
                    "vid": subnet.vlan.vid,
                    "name": subnet.vlan.get_name(),
                    "relay_vlan": None,
                    "resource_uri": f"/MAAS/api/2.0/vlans/{subnet.vlan_id}/",
                },
            },
        )

    def test_read_full(self):
        space = factory.make_Space(name="my-space")
        subnet = factory.make_Subnet(
            name="my-subnet",
            cidr="10.20.20.0/24",
            gateway_ip="10.20.20.1",
            space=space,
            dns_servers=["10.20.20.20"],
            disabled_boot_architectures=["pxe"],
            active_discovery=True,
            allow_proxy=False,
            allow_dns=False,
            description="My subnet",
            managed=False,
            rdns_mode=RDNS_MODE.DISABLED,
        )
        uri = get_subnet_uri(subnet)
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_subnet = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            parsed_subnet,
            {
                "id": subnet.id,
                "name": "my-subnet",
                "active_discovery": True,
                "allow_dns": False,
                "allow_proxy": False,
                "description": "My subnet",
                "space": "my-space",
                "cidr": "10.20.20.0/24",
                "gateway_ip": "10.20.20.1",
                "dns_servers": ["10.20.20.20"],
                "managed": False,
                "disabled_boot_architectures": ["pxe"],
                "rdns_mode": RDNS_MODE.DISABLED,
                "resource_uri": f"/MAAS/api/2.0/subnets/{subnet.id}/",
                "vlan": {
                    "id": subnet.vlan_id,
                    "dhcp_on": subnet.vlan.dhcp_on,
                    "external_dhcp": subnet.vlan.external_dhcp,
                    "fabric": subnet.vlan.fabric.get_name(),
                    "fabric_id": subnet.vlan.fabric_id,
                    "mtu": subnet.vlan.mtu,
                    "primary_rack": None,
                    "secondary_rack": None,
                    "space": "my-space",
                    "vid": subnet.vlan.vid,
                    "name": subnet.vlan.get_name(),
                    "relay_vlan": None,
                    "resource_uri": f"/MAAS/api/2.0/vlans/{subnet.vlan_id}/",
                },
            },
        )

    def test_read_404_when_bad_id(self):
        uri = reverse("subnet_handler", args=[random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_read_403_when_ambiguous(self):
        fabric = factory.make_Fabric(name="foo")
        factory.make_Subnet(fabric=fabric)
        factory.make_Subnet(fabric=fabric)
        uri = reverse("subnet_handler", args=["fabric:foo"])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        new_name = factory.make_name("subnet")
        new_rdns_mode = factory.pick_choice(RDNS_MODE_CHOICES)
        new_allow_proxy = factory.pick_bool()
        new_allow_dns = factory.pick_bool()
        new_managed = factory.pick_bool()
        uri = get_subnet_uri(subnet)
        disabled_arches = random.sample(
            [
                boot_method.name
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet or boot_method.path_prefix_http
            ],
            3,
        )

        response = self.client.put(
            uri,
            {
                "name": new_name,
                "rdns_mode": new_rdns_mode,
                "allow_proxy": new_allow_proxy,
                "allow_dns": new_allow_dns,
                "managed": new_managed,
                "disabled_boot_architectures": ",".join(disabled_arches),
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            new_name,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "name"
            ],
        )
        subnet = reload_object(subnet)
        self.assertEqual(new_name, subnet.name)
        self.assertEqual(new_rdns_mode, subnet.rdns_mode)
        self.assertEqual(new_allow_proxy, subnet.allow_proxy)
        self.assertEqual(new_allow_dns, subnet.allow_dns)
        self.assertEqual(new_managed, subnet.managed)
        self.assertCountEqual(
            disabled_arches, subnet.disabled_boot_architectures
        )

    def test_update_admin_only(self):
        subnet = factory.make_Subnet()
        new_name = factory.make_name("subnet")
        uri = get_subnet_uri(subnet)
        response = self.client.put(uri, {"name": new_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update_bool_type_using_integers(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        uri = get_subnet_uri(subnet)

        response_content = json.loads(
            self.client.get(uri).content.decode("utf-8")
        )
        initial_state_allow_dns = response_content["allow_dns"]
        initial_state_allow_proxy = response_content["allow_proxy"]

        allow_dns_str_0 = json.loads(
            self.client.put(uri, {"allow_dns": "0"}).content.decode("utf-8")
        )["allow_dns"]
        self.assertEqual(allow_dns_str_0, False)

        allow_dns_str_1 = json.loads(
            self.client.put(uri, {"allow_dns": "1"}).content.decode("utf-8")
        )["allow_dns"]
        self.assertEqual(allow_dns_str_1, True)

        allow_dns_int_0 = json.loads(
            self.client.put(uri, {"allow_dns": 0}).content.decode("utf-8")
        )["allow_dns"]
        self.assertEqual(allow_dns_int_0, False)

        allow_dns_int_1 = json.loads(
            self.client.put(uri, {"allow_dns": 1}).content.decode("utf-8")
        )["allow_dns"]
        self.assertEqual(allow_dns_int_1, True)

        allow_dns_false = json.loads(
            self.client.put(uri, QueryDict("allow_dns=false&")).content.decode(
                "utf-8"
            )
        )["allow_dns"]
        self.assertEqual(allow_dns_false, False)

        allow_dns_true = json.loads(
            self.client.put(uri, QueryDict("allow_dns=true&")).content.decode(
                "utf-8"
            )
        )["allow_dns"]
        self.assertEqual(allow_dns_true, True)

        allow_dns_false = json.loads(
            self.client.put(uri, QueryDict("allow_dns=false")).content.decode(
                "utf-8"
            )
        )["allow_dns"]
        self.assertEqual(allow_dns_false, False)

        allow_dns_true = json.loads(
            self.client.put(uri, QueryDict("allow_dns=true")).content.decode(
                "utf-8"
            )
        )["allow_dns"]
        self.assertEqual(allow_dns_true, True)

        final_state_allow_dns = json.loads(
            self.client.put(
                uri, {"allow_dns": initial_state_allow_dns}
            ).content.decode("utf-8")
        )["allow_dns"]
        self.assertEqual(initial_state_allow_dns, final_state_allow_dns)

        allow_proxy_str_0 = json.loads(
            self.client.put(uri, {"allow_proxy": "0"}).content.decode("utf-8")
        )["allow_proxy"]
        self.assertEqual(allow_proxy_str_0, False)

        allow_proxy_str_1 = json.loads(
            self.client.put(uri, {"allow_proxy": "1"}).content.decode("utf-8")
        )["allow_proxy"]
        self.assertEqual(allow_proxy_str_1, True)

        allow_proxy_false = json.loads(
            self.client.put(
                uri, QueryDict("allow_proxy=false&")
            ).content.decode("utf-8")
        )["allow_proxy"]
        self.assertEqual(allow_proxy_false, False)

        allow_proxy_true = json.loads(
            self.client.put(
                uri, QueryDict("allow_proxy=true&")
            ).content.decode("utf-8")
        )["allow_proxy"]
        self.assertEqual(allow_proxy_true, True)

        allow_proxy_false = json.loads(
            self.client.put(
                uri, QueryDict("allow_proxy=false")
            ).content.decode("utf-8")
        )["allow_proxy"]
        self.assertEqual(allow_proxy_false, False)

        allow_proxy_true = json.loads(
            self.client.put(uri, QueryDict("allow_proxy=true")).content.decode(
                "utf-8"
            )
        )["allow_proxy"]
        self.assertEqual(allow_proxy_true, True)

        allow_proxy_int_0 = json.loads(
            self.client.put(uri, {"allow_proxy": 0}).content.decode("utf-8")
        )["allow_proxy"]
        self.assertEqual(allow_proxy_int_0, False)

        allow_proxy_int_1 = json.loads(
            self.client.put(uri, {"allow_proxy": 1}).content.decode("utf-8")
        )["allow_proxy"]
        self.assertEqual(allow_proxy_int_1, True)

        final_state_allow_proxy = json.loads(
            self.client.put(
                uri, {"allow_proxy": initial_state_allow_proxy}
            ).content.decode("utf-8")
        )["allow_proxy"]
        self.assertEqual(initial_state_allow_proxy, final_state_allow_proxy)

    def test_delete_deletes_subnet(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        uri = get_subnet_uri(subnet)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(subnet))

    def test_delete_deletes_subnet_by_name(self):
        self.become_admin()
        subnet = factory.make_Subnet(name=factory.make_name("subnet"))
        uri = get_subnet_uri("name:%s" % subnet.name)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(subnet))

    def test_delete_deletes_subnet_by_cidr(self):
        self.become_admin()
        subnet = factory.make_Subnet(name=factory.make_name("subnet"))
        uri = get_subnet_uri("cidr:%s" % subnet.cidr)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(subnet))

    def test_delete_403_when_not_admin(self):
        subnet = factory.make_Subnet()
        uri = get_subnet_uri(subnet)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(subnet))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse("subnet_handler", args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )


class TestSubnetAPIAuth(APITestCase.ForAnonymous):
    """Authorization tests for subnet API."""

    def test_reserved_ip_ranges_fails_if_not_logged_in(self):
        subnet = factory.make_Subnet()
        response = self.client.get(
            get_subnet_uri(subnet), {"op": "reserved_ip_ranges"}
        )
        self.assertEqual(
            http.client.UNAUTHORIZED,
            response.status_code,
            explain_unexpected_response(http.client.UNAUTHORIZED, response),
        )

    def test_unreserved_ip_ranges_fails_if_not_logged_in(self):
        subnet = factory.make_Subnet()
        response = self.client.get(
            get_subnet_uri(subnet), {"op": "unreserved_ip_ranges"}
        )
        self.assertEqual(
            http.client.UNAUTHORIZED,
            response.status_code,
            explain_unexpected_response(http.client.UNAUTHORIZED, response),
        )


class TestSubnetReservedIPRangesAPI(APITestCase.ForUser):
    def test_returns_empty_list_for_empty_ipv4_subnet(self):
        subnet = factory.make_Subnet(version=4, dns_servers=[], gateway_ip="")
        response = self.client.get(
            get_subnet_uri(subnet), {"op": "reserved_ip_ranges"}
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual([], result)

    def test_returns_reserved_anycast_for_empty_ipv6_subnet(self):
        subnet = factory.make_Subnet(
            version=6, host_bits=80, dns_servers=[], gateway_ip=""
        )
        response = self.client.get(
            get_subnet_uri(subnet), {"op": "reserved_ip_ranges"}
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        [result] = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(1, result["num_addresses"])
        self.assertIn("rfc-4291-2.6.1", result["purpose"])

    def test_accounts_for_reserved_ip_address(self):
        subnet = factory.make_Subnet(dns_servers=[], gateway_ip="")
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        factory.make_StaticIPAddress(
            ip=ip, alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet
        )
        response = self.client.get(
            get_subnet_uri(subnet), {"op": "reserved_ip_ranges"}
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertIn(
            {
                "start": ip,
                "end": ip,
                "purpose": ["assigned-ip"],
                "num_addresses": 1,
            },
            result,
        )


class TestSubnetUnreservedIPRangesAPI(APITestCase.ForUser):
    def test_returns_full_list_for_empty_subnet(self):
        subnet = factory.make_Subnet(
            cidr=factory.make_ipv4_network(), dns_servers=[], gateway_ip=""
        )
        network = subnet.get_ipnetwork()
        response = self.client.get(
            get_subnet_uri(subnet), {"op": "unreserved_ip_ranges"}
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected_addresses = network.last - network.first + 1
        expected_first_address = inet_ntop(network.first + 1)
        if network.version == 6:
            # Don't count the IPv6 network address in num_addresses
            expected_addresses -= 1
            expected_last_address = inet_ntop(network.last)
        else:
            # Don't count the IPv4 broadcast/network addresses in num_addresses
            expected_addresses -= 2
            expected_last_address = inet_ntop(network.last - 1)
        self.assertEqual(
            [
                {
                    "start": expected_first_address,
                    "end": expected_last_address,
                    "num_addresses": expected_addresses,
                }
            ],
            result,
        )

    def _unreserved_ip_ranges_empty(self, subnet, first_address, last_address):
        """Used by the succeeding three tests to prevent duplicating the
        boilerplate that creates the requested range, then makes sure the
        unreserved_ip_ranges API call successfully returns an empty list.
        """
        factory.make_IPRange(subnet, first_address, last_address)
        response = self.client.get(
            get_subnet_uri(subnet), {"op": "unreserved_ip_ranges"}
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        self.assertEqual(result, [], str(subnet.get_ipranges_in_use()))

    def test_returns_empty_list_for_full_ipv4_subnet(self):
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr), dns_servers=[])
        network = subnet.get_ipnetwork()
        first_address = inet_ntop(network.first + 2)  # Skip gateway, network.
        last_address = inet_ntop(network.last - 1)  # Skip broadcast.
        self._unreserved_ip_ranges_empty(subnet, first_address, last_address)

    def test_returns_empty_list_for_full_ipv6_subnet(self):
        network = factory.make_ipv6_network(slash=random.randint(112, 119))
        subnet = factory.make_Subnet(cidr=str(network.cidr), dns_servers=[])
        network = subnet.get_ipnetwork()
        first_address = inet_ntop(network.first + 2)  # Skip gateway, network.
        last_address = inet_ntop(network.last)
        self._unreserved_ip_ranges_empty(subnet, first_address, last_address)

    # Slash-64 ipv6 subnets get a special range put in them - test separately.
    def test_returns_empty_list_for_full_ipv6_slash_64_subnet(self):
        network = factory.make_ipv6_network(slash=64)
        subnet = factory.make_Subnet(cidr=str(network.cidr), dns_servers=[])
        network = subnet.get_ipnetwork()
        strip64 = (network.first >> 8) << 8
        # Skip the automatically reserved range on /64's.
        first_address = inet_ntop(strip64 + 0x100000000)
        last_address = inet_ntop(network.last)
        self._unreserved_ip_ranges_empty(subnet, first_address, last_address)

    def test_accounts_for_reserved_ip_address(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_dynamic_range=False, dns_servers=[], with_router=False
        )
        network = subnet.get_ipnetwork()
        # Pick an address in the middle of the range. (that way we'll always
        # expect there to be two unreserved ranges, arranged around the
        # allocated IP address.)
        middle_ip = (network.first + network.last) // 2
        ip = inet_ntop(middle_ip)
        factory.make_StaticIPAddress(
            ip=ip, alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet
        )

        expected_addresses = network.last - network.first + 1
        expected_first_address = inet_ntop(network.first + 1)
        first_range_end = inet_ntop(middle_ip - 1)
        first_range_size = middle_ip - network.first - 1
        second_range_start = inet_ntop(middle_ip + 1)
        if network.version == 6:
            # Don't count the IPv6 network address in num_addresses
            expected_addresses -= 1
            expected_last_address = inet_ntop(network.last)
            second_range_size = network.last - middle_ip
        else:
            # Don't count the IPv4 broadcast/network addresses in num_addresses
            expected_addresses -= 2
            expected_last_address = inet_ntop(network.last - 1)
            second_range_size = network.last - middle_ip - 1

        response = self.client.get(
            get_subnet_uri(subnet), {"op": "unreserved_ip_ranges"}
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(
            result,
            [
                {
                    "start": expected_first_address,
                    "end": first_range_end,
                    "num_addresses": first_range_size,
                },
                {
                    "start": second_range_start,
                    "end": expected_last_address,
                    "num_addresses": second_range_size,
                },
            ],
            "Reserved ranges: %s" % subnet.get_ipranges_in_use(),
        )


class TestSubnetStatisticsAPI(APITestCase.ForUser):
    def test_default_does_not_include_ranges(self):
        subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet=subnet
        )
        response = self.client.get(
            get_subnet_uri(subnet), {"op": "statistics"}
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        full_iprange = subnet.get_iprange_usage()
        statistics = IPRangeStatistics(full_iprange)
        expected_result = statistics.render_json(include_ranges=False)
        self.assertEqual(expected_result, result)

    def test_with_include_ranges(self):
        subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet=subnet
        )
        response = self.client.get(
            get_subnet_uri(subnet),
            {"op": "statistics", "include_ranges": "true"},
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        full_iprange = subnet.get_iprange_usage()
        statistics = IPRangeStatistics(full_iprange)
        expected_result = statistics.render_json(include_ranges=True)
        self.assertEqual(expected_result, result)

    def test_without_include_ranges(self):
        subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet=subnet
        )
        response = self.client.get(
            get_subnet_uri(subnet),
            {"op": "statistics", "include_ranges": "false"},
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        full_iprange = subnet.get_iprange_usage()
        statistics = IPRangeStatistics(full_iprange)
        expected_result = statistics.render_json(include_ranges=False)
        self.assertEqual(expected_result, result)


class TestSubnetIPAddressesAPI(APITestCase.ForUser):
    def test_default_parameters(self):
        subnet = factory.make_Subnet()
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, status=NODE_STATUS.READY
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet=subnet, user=user
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            user=user,
            interface=node.get_boot_interface(),
        )
        response = self.client.get(
            get_subnet_uri(subnet), {"op": "ip_addresses"}
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected_result = subnet.render_json_for_related_ips(
            with_username=True, with_summary=True
        )
        self.assertEqual(expected_result, result)

    def test_with_username_false(self):
        subnet = factory.make_Subnet()
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, status=NODE_STATUS.READY
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet=subnet, user=user
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            user=user,
            interface=node.get_boot_interface(),
        )
        response = self.client.get(
            get_subnet_uri(subnet),
            {"op": "ip_addresses", "with_username": "false"},
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected_result = subnet.render_json_for_related_ips(
            with_username=False, with_summary=True
        )
        self.assertEqual(expected_result, result)

    def test_with_summary_false(self):
        subnet = factory.make_Subnet()
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, status=NODE_STATUS.READY
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet=subnet, user=user
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            user=user,
            interface=node.get_boot_interface(),
        )
        response = self.client.get(
            get_subnet_uri(subnet),
            {"op": "ip_addresses", "with_summary": "false"},
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected_result = subnet.render_json_for_related_ips(
            with_username=True, with_summary=False
        )
        self.assertEqual(expected_result, result)

    def test_with_deprecated_node_summary_false(self):
        subnet = factory.make_Subnet()
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, status=NODE_STATUS.READY
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet=subnet, user=user
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet,
            user=user,
            interface=node.get_boot_interface(),
        )
        response = self.client.get(
            get_subnet_uri(subnet),
            {"op": "ip_addresses", "with_node_summary": "false"},
        )
        self.assertEqual(
            http.client.OK,
            response.status_code,
            explain_unexpected_response(http.client.OK, response),
        )
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        expected_result = subnet.render_json_for_related_ips(
            with_username=True, with_summary=False
        )
        self.assertEqual(expected_result, result)
