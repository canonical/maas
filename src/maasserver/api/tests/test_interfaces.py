# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for NodeInterfaces API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json
import random

from django.core.urlresolvers import reverse
from maasserver.enum import INTERFACE_TYPE
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from testtools.matchers import (
    ContainsDict,
    Equals,
)


def get_node_interfaces_uri(node):
    """Return a Node's interfaces URI on the API."""
    return reverse(
        'node_interfaces_handler', args=[node.system_id])


def get_node_interface_uri(interface, node=None):
    """Return a Node's interface URI on the API."""
    if node is None:
        node = interface.get_node()
    return reverse(
        'node_interface_handler', args=[node.system_id, interface.id])


def make_complex_interface(node):
    """Makes interface with parents and children."""
    nic_0_mac = factory.make_MACAddress(node=node, iftype=None)
    nic_1_mac = factory.make_MACAddress(node=node, iftype=None)
    fabric = factory.make_Fabric()
    vlan_5 = factory.make_VLAN(vid=5, fabric=fabric)
    nic_0 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL, mac=nic_0_mac, vlan=vlan_5)
    nic_1 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL, mac=nic_1_mac, vlan=vlan_5)
    parents = [nic_0, nic_1]
    bond_interface = factory.make_Interface(
        INTERFACE_TYPE.BOND, mac=nic_0_mac, vlan=vlan_5,
        parents=parents)
    vlan_10 = factory.make_VLAN(vid=10, fabric=fabric)
    vlan_nic_10 = factory.make_Interface(
        INTERFACE_TYPE.VLAN, mac=nic_0_mac, vlan=vlan_10,
        parents=[bond_interface])
    vlan_11 = factory.make_VLAN(vid=11, fabric=fabric)
    vlan_nic_11 = factory.make_Interface(
        INTERFACE_TYPE.VLAN, mac=nic_0_mac, vlan=vlan_11,
        parents=[bond_interface])
    return bond_interface, parents, [vlan_nic_10, vlan_nic_11]


class TestNodeInterfacesAPI(APITestCase):

    def test_handler_path(self):
        node = factory.make_Node()
        self.assertEqual(
            '/api/1.0/nodes/%s/interfaces/' % (node.system_id),
            get_node_interfaces_uri(node))

    def test_read(self):
        node = factory.make_Node()
        bond, parents, children = make_complex_interface(node)
        uri = get_node_interfaces_uri(node)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        expected_ids = [
            nic.id
            for nic in [bond] + parents + children
            ]
        result_ids = [
            nic["id"]
            for nic in json.loads(response.content)
            ]
        self.assertItemsEqual(expected_ids, result_ids)


class TestNodeInterfaceAPI(APITestCase):

    def test_handler_path(self):
        node = factory.make_Node(mac=True)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac=node.get_pxe_mac())
        self.assertEqual(
            '/api/1.0/nodes/%s/interfaces/%s/' % (
                node.system_id, interface.id),
            get_node_interface_uri(interface, node=node))

    def test_read(self):
        node = factory.make_Node()
        bond, parents, children = make_complex_interface(node)
        uri = get_node_interface_uri(bond)
        response = self.client.get(uri)

        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_interface = json.loads(response.content)
        self.assertThat(parsed_interface, ContainsDict({
            "id": Equals(bond.id),
            "name": Equals(bond.name),
            "type": Equals(bond.type),
            "vlan": ContainsDict({
                "id": Equals(bond.vlan.id),
                }),
            "mac_address": Equals("%s" % bond.mac.mac_address),
            "tags": Equals(bond.tags),
            "resource_uri": Equals(get_node_interface_uri(bond)),
            }))
        self.assertEquals(sorted(
            nic.name
            for nic in parents
            ), parsed_interface["parents"])
        self.assertEquals(sorted(
            nic.name
            for nic in children
            ), parsed_interface["children"])

    def test_read_404_when_invalid_id(self):
        node = factory.make_Node()
        uri = reverse(
            'node_interface_handler',
            args=[node.system_id, random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_delete_deletes_interface(self):
        self.become_admin()
        node = factory.make_Node(mac=True)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac=node.get_pxe_mac())
        uri = get_node_interface_uri(interface)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NO_CONTENT, response.status_code, response.content)
        self.assertIsNone(reload_object(interface))

    def test_delete_403_when_not_admin(self):
        node = factory.make_Node(mac=True)
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, mac=node.get_pxe_mac())
        uri = get_node_interface_uri(interface)
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)
        self.assertIsNotNone(reload_object(interface))

    def test_delete_404_when_invalid_id(self):
        node = factory.make_Node()
        uri = reverse(
            'node_interface_handler',
            args=[node.system_id, random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)
