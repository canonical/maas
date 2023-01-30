# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `Network` API."""


import http.client

from django.urls import reverse

from maasserver.api.networks import convert_to_network_name
from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, NODE_STATUS
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes


class TestNetwork(APITestCase.ForUser):
    def get_url(self, subnet):
        """Return the URL for the network of the given subnet."""
        return reverse("network_handler", args=["subnet-%d" % subnet.id])

    def test_handler_path(self):
        subnet = factory.make_Subnet()
        self.assertEqual(
            "/MAAS/api/2.0/networks/subnet-%d/" % subnet.id,
            self.get_url(subnet),
        )

    def test_POST_is_prohibited(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        response = self.client.post(
            self.get_url(subnet), {"description": "New description"}
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_GET_returns_network(self):
        subnet = factory.make_Subnet()

        response = self.client.get(self.get_url(subnet))
        self.assertEqual(http.client.OK, response.status_code)

        parsed_result = json_load_bytes(response.content)
        cidr = subnet.get_ipnetwork()
        self.assertEqual(
            (
                "subnet-%d" % subnet.id,
                str(cidr.ip),
                str(cidr.netmask),
                subnet.vlan.vid,
                subnet.name,
                subnet.gateway_ip,
                subnet.dns_servers,
                reverse("network_handler", args=["subnet-%d" % subnet.id]),
            ),
            (
                parsed_result["name"],
                parsed_result["ip"],
                parsed_result["netmask"],
                parsed_result["vlan_tag"],
                parsed_result["description"],
                parsed_result["default_gateway"],
                parsed_result["dns_servers"],
                parsed_result["resource_uri"],
            ),
        )

    def test_GET_returns_404_for_unknown_network(self):
        self.assertEqual(
            http.client.NOT_FOUND,
            self.client.get(
                reverse("network_handler", args=["subnet-unknown"])
            ).status_code,
        )

    def test_PUT_returns_410(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        response = self.client.put(self.get_url(subnet))
        self.assertEqual(http.client.GONE, response.status_code)

    def test_DELETE_returns_410(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        response = self.client.delete(self.get_url(subnet))
        self.assertEqual(http.client.GONE, response.status_code)

    def test_POST_connect_macs_returns_410(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        response = self.client.post(
            self.get_url(subnet), {"op": "connect_macs"}
        )
        self.assertEqual(http.client.GONE, response.status_code)

    def test_POST_disconnect_macs_returns_410(self):
        self.become_admin()
        subnet = factory.make_Subnet()
        response = self.client.post(
            self.get_url(subnet), {"op": "disconnect_macs"}
        )
        self.assertEqual(http.client.GONE, response.status_code)


class TestListConnectedMACs(APITestCase.ForUser):
    """Tests for /api/2.0/network/s<network>/?op=list_connected_macs."""

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

    def request_connected_macs(self, subnet):
        """Request and return the MAC addresses attached to `subnet`."""
        url = reverse(
            "network_handler", args=[convert_to_network_name(subnet)]
        )
        response = self.client.get(url, {"op": "list_connected_macs"})
        self.assertEqual(http.client.OK, response.status_code)
        return json_load_bytes(response.content)

    def extract_macs(self, returned_macs):
        """Extract the textual MAC addresses from an API response."""
        return [item["mac_address"] for item in returned_macs]

    def test_returns_connected_macs(self):
        subnet = factory.make_Subnet()
        interfaces = [
            self.make_interface(subnets=[subnet], owner=self.user)
            for _ in range(3)
        ]
        self.assertEqual(
            {interface.mac_address for interface in interfaces},
            set(self.extract_macs(self.request_connected_macs(subnet))),
        )

    def test_ignores_unconnected_macs(self):
        self.make_interface(subnets=[factory.make_Subnet()], owner=self.user)
        self.make_interface(subnets=[], owner=self.user)
        self.assertEqual(
            [], self.request_connected_macs(factory.make_Subnet())
        )

    def test_includes_MACs_for_nodes_visible_to_user(self):
        subnet = factory.make_Subnet()
        interface = self.make_interface(subnets=[subnet], owner=self.user)
        self.assertEqual(
            [interface.mac_address],
            self.extract_macs(self.request_connected_macs(subnet)),
        )

    def test_excludes_MACs_for_nodes_not_visible_to_user(self):
        subnet = factory.make_Subnet()
        self.make_interface(subnets=[subnet])
        self.assertEqual([], self.request_connected_macs(subnet))

    def test_returns_sorted_MACs(self):
        subnet = factory.make_Subnet()
        interfaces = [
            self.make_interface(
                subnets=[subnet],
                node=factory.make_Node(sortable_name=True),
                owner=self.user,
            )
            for _ in range(4)
        ]
        # Create MACs connected to the same node.
        interfaces = interfaces + [
            self.make_interface(
                subnets=[subnet],
                owner=self.user,
                node=interfaces[0].node_config.node,
            )
            for _ in range(3)
        ]
        sorted_interfaces = sorted(
            interfaces,
            key=lambda x: (
                x.node_config.node.hostname.lower(),
                x.mac_address,
            ),
        )
        self.assertEqual(
            [nic.mac_address for nic in sorted_interfaces],
            self.extract_macs(self.request_connected_macs(subnet)),
        )
