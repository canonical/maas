# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for networks API."""

import http.client

from django.urls import reverse

from maasserver.api.networks import convert_to_network_name
from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, NODE_STATUS
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes


class TestNetworksAPI(APITestCase.ForUser):
    def make_interface(self, subnets=None, owner=None, node=None):
        """Create a Interface.

        :param subnets: Optional list of `Subnet` objects to connect the
            interface to.  If omitted, the interface will not be connected to
            any subnets.
        :param node: Optional node that will have this interface.
            If omitted, one will be created.
        :param owner: Optional owner for the node that will have this MAC
            address.  If omitted, one will be created.  The node will be in
            the "allocated" state.  This parameter is ignored if a node is
            provided.
        """
        if subnets is None:
            subnets = []
        if owner is None:
            owner = factory.make_User()
        if node is None:
            node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=owner)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        for subnet in subnets:
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DHCP,
                ip="",
                subnet=subnet,
                interface=interface,
            )
        return interface

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/networks/", reverse("networks_handler")
        )

    def test_POST_returns_410(self):
        self.become_admin()
        response = self.client.post(reverse("networks_handler"))
        self.assertEqual(http.client.GONE, response.status_code)

    def test_GET_returns_networks(self):
        subnet = factory.make_Subnet()
        subnet_cidr = subnet.get_ipnetwork()
        response = self.client.get(reverse("networks_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        parsed_result = json_load_bytes(response.content)
        self.assertEqual(1, len(parsed_result))
        [returned_subnet] = parsed_result
        self.assertEqual(
            {
                "name": "subnet-%d" % subnet.id,
                "ip": str(subnet_cidr.ip),
                "netmask": str(subnet_cidr.netmask),
                "vlan_tag": subnet.vlan.vid,
                "description": subnet.name,
                "default_gateway": subnet.gateway_ip,
                "dns_servers": subnet.dns_servers,
                "resource_uri": reverse(
                    "network_handler", args=["subnet-%d" % subnet.id]
                ),
            },
            returned_subnet,
        )

    def test_GET_returns_empty_if_no_subnets(self):
        response = self.client.get(reverse("networks_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual([], json_load_bytes(response.content))

    def test_GET_sorts_by_name(self):
        subnets = [
            factory.make_Subnet(name=factory.make_name("subnet").lower())
            for _ in range(3)
        ]
        response = self.client.get(reverse("networks_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        self.assertEqual(
            sorted(convert_to_network_name(subnet) for subnet in subnets),
            [network["name"] for network in json_load_bytes(response.content)],
        )

    def test_GET_filters_by_node(self):
        subnets = [factory.make_Subnet() for _ in range(5)]
        interface = self.make_interface(subnets=subnets[1:3])
        node = interface.node_config.node
        response = self.client.get(
            reverse("networks_handler"), {"node": [node.system_id]}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        self.assertEqual(
            {convert_to_network_name(subnet) for subnet in subnets[1:3]},
            {network["name"] for network in json_load_bytes(response.content)},
        )

    def test_GET_combines_node_filters_as_intersection_of_networks(self):
        subnets = [factory.make_Subnet() for _ in range(5)]
        interface1 = self.make_interface(subnets=subnets[1:3])
        interface2 = self.make_interface(subnets=subnets[2:4])
        node1 = interface1.node_config.node
        node2 = interface2.node_config.node
        # Attach another interface to node1.
        self.make_interface(subnets=subnets[1:2], node=node1)

        response = self.client.get(
            reverse("networks_handler"),
            {"node": [node1.system_id, node2.system_id]},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )

        self.assertEqual(
            {convert_to_network_name(subnets[2])},
            {network["name"] for network in json_load_bytes(response.content)},
        )

    def test_GET_fails_if_filtering_by_nonexistent_node(self):
        bad_system_id = factory.make_name("no_node")
        response = self.client.get(
            reverse("networks_handler"), {"node": [bad_system_id]}
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertEqual(
            {"node": ["Unknown node(s): %s." % bad_system_id]},
            json_load_bytes(response.content),
        )

    def test_GET_ignores_duplicates(self):
        subnet = factory.make_Subnet()
        interface = self.make_interface(subnets=[subnet])
        node = interface.node_config.node
        response = self.client.get(
            reverse("networks_handler"),
            {"node": [node.system_id, node.system_id]},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            {convert_to_network_name(subnet)},
            {network["name"] for network in json_load_bytes(response.content)},
        )
