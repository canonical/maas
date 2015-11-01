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
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
)
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from testtools.matchers import (
    ContainsDict,
    Equals,
    MatchesDict,
    MatchesListwise,
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
    fabric = factory.make_Fabric()
    vlan_5 = factory.make_VLAN(vid=5, fabric=fabric)
    nic_0 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL, vlan=vlan_5, node=node)
    nic_1 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL, vlan=vlan_5, node=node)
    parents = [nic_0, nic_1]
    bond_interface = factory.make_Interface(
        INTERFACE_TYPE.BOND, mac_address=nic_0.mac_address, vlan=vlan_5,
        parents=parents)
    vlan_10 = factory.make_VLAN(vid=10, fabric=fabric)
    vlan_nic_10 = factory.make_Interface(
        INTERFACE_TYPE.VLAN, vlan=vlan_10, parents=[bond_interface])
    vlan_11 = factory.make_VLAN(vid=11, fabric=fabric)
    vlan_nic_11 = factory.make_Interface(
        INTERFACE_TYPE.VLAN, vlan=vlan_11, parents=[bond_interface])
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

    def test_create_physical(self):
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(status=status)
            mac = factory.make_mac_address()
            name = factory.make_name("eth")
            vlan = factory.make_VLAN()
            tags = [
                factory.make_name("tag")
                for _ in range(3)
            ]
            uri = get_node_interfaces_uri(node)
            response = self.client.post(uri, {
                "op": "create_physical",
                "mac_address": mac,
                "name": name,
                "vlan": vlan.id,
                "tags": ",".join(tags),
                })

            self.assertEqual(
                httplib.OK, response.status_code, response.content)
            self.assertThat(json.loads(response.content), ContainsDict({
                "mac_address": Equals(mac),
                "name": Equals(name),
                "vlan": ContainsDict({
                    "id": Equals(vlan.id),
                    }),
                "type": Equals("physical"),
                "tags": Equals(tags),
                "enabled": Equals(True),
                }))

    def test_create_physical_disabled(self):
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(status=status)
            mac = factory.make_mac_address()
            name = factory.make_name("eth")
            vlan = factory.make_VLAN()
            tags = [
                factory.make_name("tag")
                for _ in range(3)
            ]
            uri = get_node_interfaces_uri(node)
            response = self.client.post(uri, {
                "op": "create_physical",
                "mac_address": mac,
                "name": name,
                "vlan": vlan.id,
                "tags": ",".join(tags),
                "enabled": False,
                })

            self.assertEqual(
                httplib.OK, response.status_code, response.content)
            self.assertThat(json.loads(response.content), ContainsDict({
                "mac_address": Equals(mac),
                "name": Equals(name),
                "vlan": ContainsDict({
                    "id": Equals(vlan.id),
                    }),
                "type": Equals("physical"),
                "tags": Equals(tags),
                "enabled": Equals(False),
                }))

    def test_create_physical_requires_admin(self):
        node = factory.make_Node()
        mac = factory.make_mac_address()
        name = factory.make_name("eth")
        vlan = factory.make_VLAN()
        uri = get_node_interfaces_uri(node)
        response = self.client.post(uri, {
            "op": "create_physical",
            "mac_address": mac,
            "name": name,
            "vlan": vlan.id,
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_create_physical_409_when_not_ready_or_broken(self):
        self.become_admin()
        for status in (
                NODE_STATUS.NEW,
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.FAILED_COMMISSIONING,
                NODE_STATUS.MISSING,
                NODE_STATUS.RESERVED,
                NODE_STATUS.ALLOCATED,
                NODE_STATUS.DEPLOYING,
                NODE_STATUS.DEPLOYED,
                NODE_STATUS.RETIRED,
                NODE_STATUS.FAILED_DEPLOYMENT,
                NODE_STATUS.RELEASING,
                NODE_STATUS.FAILED_RELEASING,
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.FAILED_DISK_ERASING
        ):
            node = factory.make_Node(status=status)
            mac = factory.make_mac_address()
            name = factory.make_name("eth")
            vlan = factory.make_VLAN()
            uri = get_node_interfaces_uri(node)
            response = self.client.post(uri, {
                "op": "create_physical",
                "mac_address": mac,
                "name": name,
                "vlan": vlan.id,
                })
            self.assertEqual(
                httplib.CONFLICT, response.status_code, response.content)

    def test_create_physical_requires_mac_name_and_vlan(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        uri = get_node_interfaces_uri(node)
        response = self.client.post(uri, {
            "op": "create_physical",
            })
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEquals({
            "mac_address": ["This field is required."],
            "name": ["This field is required."],
            "vlan": ["This field is required."],
            }, json.loads(response.content))

    def test_create_physical_doesnt_allow_mac_already_register(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        interface_on_other_node = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL)
        name = factory.make_name("eth")
        vlan = factory.make_VLAN()
        uri = get_node_interfaces_uri(node)
        response = self.client.post(uri, {
            "op": "create_physical",
            "mac_address": "%s" % interface_on_other_node.mac_address,
            "name": name,
            "vlan": vlan.id,
            })
        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEquals({
            "mac_address": [
                "This MAC address is already in use by %s." % (
                    interface_on_other_node.node.hostname)],
            }, json.loads(response.content))

    def test_create_bond(self):
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(status=status)
            vlan = factory.make_VLAN()
            parent_1_iface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node)
            parent_2_iface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node)
            name = factory.make_name("bond")
            tags = [
                factory.make_name("tag")
                for _ in range(3)
            ]
            uri = get_node_interfaces_uri(node)
            response = self.client.post(uri, {
                "op": "create_bond",
                "mac_address": "%s" % parent_1_iface.mac_address,
                "name": name,
                "vlan": vlan.id,
                "parents": [parent_1_iface.id, parent_2_iface.id],
                "tags": ",".join(tags),
                })

            self.assertEqual(
                httplib.OK, response.status_code, response.content)
            parsed_interface = json.loads(response.content)
            self.assertThat(parsed_interface, ContainsDict({
                "mac_address": Equals("%s" % parent_1_iface.mac_address),
                "name": Equals(name),
                "vlan": ContainsDict({
                    "id": Equals(vlan.id),
                    }),
                "type": Equals("bond"),
                "tags": Equals(tags),
                }))
            self.assertItemsEqual([
                parent_1_iface.name,
                parent_2_iface.name,
                ], parsed_interface['parents'])

    def test_create_bond_requires_admin(self):
        node = factory.make_Node()
        vlan = factory.make_VLAN()
        parent_1_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node)
        parent_2_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node)
        name = factory.make_name("bond")
        uri = get_node_interfaces_uri(node)
        response = self.client.post(uri, {
            "op": "create_bond",
            "mac": "%s" % parent_1_iface.mac_address,
            "name": name,
            "vlan": vlan.id,
            "parents": [parent_1_iface.id, parent_2_iface.id],
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_create_bond_409_when_not_ready_or_broken(self):
        self.become_admin()
        for status in (
                NODE_STATUS.NEW,
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.FAILED_COMMISSIONING,
                NODE_STATUS.MISSING,
                NODE_STATUS.RESERVED,
                NODE_STATUS.ALLOCATED,
                NODE_STATUS.DEPLOYING,
                NODE_STATUS.DEPLOYED,
                NODE_STATUS.RETIRED,
                NODE_STATUS.FAILED_DEPLOYMENT,
                NODE_STATUS.RELEASING,
                NODE_STATUS.FAILED_RELEASING,
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.FAILED_DISK_ERASING
        ):
            node = factory.make_Node(status=status)
            vlan = factory.make_VLAN()
            parent_1_iface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node)
            parent_2_iface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, vlan=vlan, node=node)
            name = factory.make_name("bond")
            uri = get_node_interfaces_uri(node)
            response = self.client.post(uri, {
                "op": "create_bond",
                "mac": "%s" % parent_1_iface.mac_address,
                "name": name,
                "vlan": vlan.id,
                "parents": [parent_1_iface.id, parent_2_iface.id],
                })
            self.assertEqual(
                httplib.CONFLICT, response.status_code, response.content)

    def test_create_bond_requires_name_vlan_and_parents(self):
        self.become_admin()
        node = factory.make_Node(status=NODE_STATUS.READY)
        uri = get_node_interfaces_uri(node)
        response = self.client.post(uri, {
            "op": "create_bond",
            })

        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEquals({
            "mac_address": ["This field cannot be blank."],
            "name": ["This field is required."],
            "vlan": ["This field is required."],
            "parents": ["A Bond interface must have one or more parents."],
            }, json.loads(response.content))

    def test_create_vlan(self):
        self.become_admin()
        node = factory.make_Node()
        untagged_vlan = factory.make_VLAN()
        parent_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=untagged_vlan, node=node)
        tagged_vlan = factory.make_VLAN()
        tags = [
            factory.make_name("tag")
            for _ in range(3)
        ]
        uri = get_node_interfaces_uri(node)
        response = self.client.post(uri, {
            "op": "create_vlan",
            "vlan": tagged_vlan.id,
            "parent": parent_iface.id,
            "tags": ",".join(tags),
            })

        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_interface = json.loads(response.content)
        self.assertThat(parsed_interface, ContainsDict({
            "mac_address": Equals("%s" % parent_iface.mac_address),
            "vlan": ContainsDict({
                "id": Equals(tagged_vlan.id),
                }),
            "type": Equals("vlan"),
            "parents": Equals([parent_iface.name]),
            "tags": Equals(tags),
            }))

    def test_create_vlan_requires_admin(self):
        node = factory.make_Node()
        untagged_vlan = factory.make_VLAN()
        parent_iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=untagged_vlan, node=node)
        tagged_vlan = factory.make_VLAN()
        uri = get_node_interfaces_uri(node)
        response = self.client.post(uri, {
            "op": "create_vlan",
            "vlan": tagged_vlan.id,
            "parent": parent_iface.id,
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_create_vlan_requires_vlan_and_parent(self):
        self.become_admin()
        node = factory.make_Node()
        uri = get_node_interfaces_uri(node)
        response = self.client.post(uri, {
            "op": "create_vlan",
            })

        self.assertEqual(
            httplib.BAD_REQUEST, response.status_code, response.content)
        self.assertEquals({
            "vlan": ["This field is required."],
            "parent": ["A VLAN interface must have exactly one parent."],
            }, json.loads(response.content))


class TestNodeInterfaceAPI(APITestCase):

    def test_handler_path(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        self.assertEqual(
            '/api/1.0/nodes/%s/interfaces/%s/' % (
                node.system_id, interface.id),
            get_node_interface_uri(interface, node=node))

    def test_read(self):
        node = factory.make_Node()
        bond, parents, children = make_complex_interface(node)
        # Add some known links to the bond interface.

        # First link is a DHCP link.
        links = []
        dhcp_subnet = factory.make_Subnet()
        dhcp_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="",
            subnet=dhcp_subnet, interface=bond)
        discovered_ip = factory.pick_ip_in_network(
            dhcp_subnet.get_ipnetwork())
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=discovered_ip,
            subnet=dhcp_subnet, interface=bond)
        links.append(
            MatchesDict({
                "id": Equals(dhcp_ip.id),
                "mode": Equals(INTERFACE_LINK_TYPE.DHCP),
                "subnet": ContainsDict({
                    "id": Equals(dhcp_subnet.id)
                    }),
                "ip_address": Equals(discovered_ip),
            }))

        # Second link is a STATIC ip link.
        static_subnet = factory.make_Subnet()
        static_ip = factory.pick_ip_in_network(static_subnet.get_ipnetwork())
        sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=static_ip,
            subnet=static_subnet, interface=bond)
        links.append(
            MatchesDict({
                "id": Equals(sip.id),
                "mode": Equals(INTERFACE_LINK_TYPE.STATIC),
                "ip_address": Equals(static_ip),
                "subnet": ContainsDict({
                    "id": Equals(static_subnet.id)
                    })
            }))

        # Third link is just a LINK_UP. In reality this cannot exist while the
        # other two links exist but for testing we allow it. If validation of
        # the StaticIPAddress model ever included this check, which it
        # probably should then this will fail and cause this test to break.
        link_subnet = factory.make_Subnet()
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=link_subnet, interface=bond)
        links.append(
            MatchesDict({
                "id": Equals(link_ip.id),
                "mode": Equals(INTERFACE_LINK_TYPE.LINK_UP),
                "subnet": ContainsDict({
                    "id": Equals(link_subnet.id)
                    })
            }))

        # Add MTU parameter.
        bond.params = {
            "mtu": random.randint(800, 2000)
        }
        bond.save()

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
            "mac_address": Equals("%s" % bond.mac_address),
            "tags": Equals(bond.tags),
            "resource_uri": Equals(get_node_interface_uri(bond)),
            "params": Equals(bond.params),
        }))
        self.assertEquals(sorted(
            nic.name
            for nic in parents
            ), parsed_interface["parents"])
        self.assertEquals(sorted(
            nic.name
            for nic in children
            ), parsed_interface["children"])
        self.assertThat(parsed_interface["links"], MatchesListwise(links))
        json_discovered = parsed_interface["discovered"][0]
        self.assertEquals(dhcp_subnet.id, json_discovered["subnet"]["id"])
        self.assertEquals(discovered_ip, json_discovered["ip_address"])

    def test_read_404_when_invalid_id(self):
        node = factory.make_Node()
        uri = reverse(
            'node_interface_handler',
            args=[node.system_id, random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_update_physical_interface(self):
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(status=status)
            interface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node)
            new_name = factory.make_name("name")
            new_vlan = factory.make_VLAN()
            uri = get_node_interface_uri(interface)
            response = self.client.put(uri, {
                "name": new_name,
                "vlan": new_vlan.id,
                })
            self.assertEqual(
                httplib.OK, response.status_code, response.content)
            parsed_interface = json.loads(response.content)
            self.assertEquals(new_name, parsed_interface["name"])
            self.assertEquals(new_vlan.id, parsed_interface["vlan"]["id"])

    def test_update_bond_interface(self):
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(status=status)
            bond, [nic_0, nic_1], [vlan_10, vlan_11] = make_complex_interface(
                node)
            uri = get_node_interface_uri(bond)
            response = self.client.put(uri, {
                "parents": [nic_0.id],
                })
            self.assertEqual(
                httplib.OK, response.status_code, response.content)
            parsed_interface = json.loads(response.content)
            self.assertEquals([nic_0.name], parsed_interface["parents"])

    def test_update_vlan_interface(self):
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(status=status)
            bond, [nic_0, nic_1], [vlan_10, vlan_11] = make_complex_interface(
                node)
            physical_interface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node)
            uri = get_node_interface_uri(vlan_10)
            response = self.client.put(uri, {
                "parent": physical_interface.id,
                })
            self.assertEqual(
                httplib.OK, response.status_code, response.content)
            parsed_interface = json.loads(response.content)
            self.assertEquals(
                [physical_interface.name], parsed_interface["parents"])

    def test_update_requires_admin(self):
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        new_name = factory.make_name("name")
        uri = get_node_interface_uri(interface)
        response = self.client.put(uri, {
            "name": new_name,
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_read_409_when_not_ready_or_broken(self):
        self.become_admin()
        for status in (
                NODE_STATUS.NEW,
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.FAILED_COMMISSIONING,
                NODE_STATUS.MISSING,
                NODE_STATUS.RESERVED,
                NODE_STATUS.ALLOCATED,
                NODE_STATUS.DEPLOYING,
                NODE_STATUS.DEPLOYED,
                NODE_STATUS.RETIRED,
                NODE_STATUS.FAILED_DEPLOYMENT,
                NODE_STATUS.RELEASING,
                NODE_STATUS.FAILED_RELEASING,
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.FAILED_DISK_ERASING
        ):
            node = factory.make_Node(interface=True, status=status)
            interface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node)
            new_name = factory.make_name("name")
            uri = get_node_interface_uri(interface)
            response = self.client.put(uri, {
                "name": new_name,
                })
            self.assertEqual(
                httplib.CONFLICT, response.status_code, response.content)

    def test_delete_deletes_interface(self):
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_node_interface_uri(interface)
            response = self.client.delete(uri)
            self.assertEqual(
                httplib.NO_CONTENT, response.status_code, response.content)
            self.assertIsNone(reload_object(interface))

    def test_delete_403_when_not_admin(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
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

    def test_delete_409_when_not_ready_or_broken(self):
        self.become_admin()
        for status in (
                NODE_STATUS.NEW,
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.FAILED_COMMISSIONING,
                NODE_STATUS.MISSING,
                NODE_STATUS.RESERVED,
                NODE_STATUS.ALLOCATED,
                NODE_STATUS.DEPLOYING,
                NODE_STATUS.DEPLOYED,
                NODE_STATUS.RETIRED,
                NODE_STATUS.FAILED_DEPLOYMENT,
                NODE_STATUS.RELEASING,
                NODE_STATUS.FAILED_RELEASING,
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.FAILED_DISK_ERASING
        ):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_node_interface_uri(interface)
            response = self.client.delete(uri)
            self.assertEqual(
                httplib.CONFLICT, response.status_code, response.content)

    def test_link_subnet_creates_link(self):
        # The form that is used is fully tested in test_forms_interface_link.
        # This just tests that the form is saved and the updated interface
        # is returned.
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_node_interface_uri(interface)
            response = self.client.post(uri, {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.DHCP,
                })
            self.assertEqual(
                httplib.OK, response.status_code, response.content)
            parsed_response = json.loads(response.content)
            self.assertThat(
                parsed_response["links"][0], ContainsDict({
                    "mode": Equals(INTERFACE_LINK_TYPE.DHCP),
                    }))

    def test_link_subnet_raises_error(self):
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_node_interface_uri(interface)
            response = self.client.post(uri, {
                "op": "link_subnet",
                })
            self.assertEqual(
                httplib.BAD_REQUEST, response.status_code, response.content)
            self.assertEquals({
                "mode": ["This field is required."]
                }, json.loads(response.content))

    def test_link_subnet_requries_admin(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        uri = get_node_interface_uri(interface)
        response = self.client.post(uri, {
            "op": "link_subnet",
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_link_subnet_409_when_not_ready_or_broken(self):
        self.become_admin()
        for status in (
                NODE_STATUS.NEW,
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.FAILED_COMMISSIONING,
                NODE_STATUS.MISSING,
                NODE_STATUS.RESERVED,
                NODE_STATUS.ALLOCATED,
                NODE_STATUS.DEPLOYING,
                NODE_STATUS.DEPLOYED,
                NODE_STATUS.RETIRED,
                NODE_STATUS.FAILED_DEPLOYMENT,
                NODE_STATUS.RELEASING,
                NODE_STATUS.FAILED_RELEASING,
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.FAILED_DISK_ERASING
        ):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_node_interface_uri(interface)
            response = self.client.post(uri, {
                "op": "link_subnet",
                "mode": INTERFACE_LINK_TYPE.DHCP,
                })
            self.assertEqual(
                httplib.CONFLICT, response.status_code, response.content)

    def test_unlink_subnet_deletes_link(self):
        # The form that is used is fully tested in test_forms_interface_link.
        # This just tests that the form is saved and the updated interface
        # is returned.
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            subnet = factory.make_Subnet()
            dhcp_ip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DHCP, ip="",
                subnet=subnet, interface=interface)
            uri = get_node_interface_uri(interface)
            response = self.client.post(uri, {
                "op": "unlink_subnet",
                "id": dhcp_ip.id,
                })
            self.assertEqual(
                httplib.OK, response.status_code, response.content)
            self.assertIsNone(reload_object(dhcp_ip))

    def test_unlink_subnet_raises_error(self):
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_node_interface_uri(interface)
            response = self.client.post(uri, {
                "op": "unlink_subnet",
                })
            self.assertEqual(
                httplib.BAD_REQUEST, response.status_code, response.content)
            self.assertEquals({
                "id": ["This field is required."]
                }, json.loads(response.content))

    def test_unlink_subnet_requries_admin(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        uri = get_node_interface_uri(interface)
        response = self.client.post(uri, {
            "op": "unlink_subnet",
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_unlink_subnet_409_when_not_ready_or_broken(self):
        self.become_admin()
        for status in (
                NODE_STATUS.NEW,
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.FAILED_COMMISSIONING,
                NODE_STATUS.MISSING,
                NODE_STATUS.RESERVED,
                NODE_STATUS.ALLOCATED,
                NODE_STATUS.DEPLOYING,
                NODE_STATUS.DEPLOYED,
                NODE_STATUS.RETIRED,
                NODE_STATUS.FAILED_DEPLOYMENT,
                NODE_STATUS.RELEASING,
                NODE_STATUS.FAILED_RELEASING,
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.FAILED_DISK_ERASING
        ):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_node_interface_uri(interface)
            response = self.client.post(uri, {
                "op": "unlink_subnet",
                })
            self.assertEqual(
                httplib.CONFLICT, response.status_code, response.content)

    def test_set_default_gateway_sets_gateway_link_ipv4_on_node(self):
        # The form that is used is fully tested in test_forms_interface_link.
        # This just tests that the form is saved and the node link is created.
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            network = factory.make_ipv4_network()
            subnet = factory.make_Subnet(
                cidr=unicode(network.cidr), vlan=interface.vlan)
            link_ip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO, ip="",
                subnet=subnet, interface=interface)
            uri = get_node_interface_uri(interface)
            response = self.client.post(uri, {
                "op": "set_default_gateway",
                "link_id": link_ip.id
                })
            self.assertEqual(
                httplib.OK, response.status_code, response.content)
            self.assertEqual(link_ip, reload_object(node).gateway_link_ipv4)

    def test_set_default_gateway_sets_gateway_link_ipv6_on_node(self):
        # The form that is used is fully tested in test_forms_interface_link.
        # This just tests that the form is saved and the node link is created.
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            network = factory.make_ipv6_network()
            subnet = factory.make_Subnet(
                cidr=unicode(network.cidr), vlan=interface.vlan)
            link_ip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO, ip="",
                subnet=subnet, interface=interface)
            uri = get_node_interface_uri(interface)
            response = self.client.post(uri, {
                "op": "set_default_gateway",
                "link_id": link_ip.id
                })
            self.assertEqual(
                httplib.OK, response.status_code, response.content)
            self.assertEqual(link_ip, reload_object(node).gateway_link_ipv6)

    def test_set_default_gateway_raises_error(self):
        self.become_admin()
        for status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_node_interface_uri(interface)
            response = self.client.post(uri, {
                "op": "set_default_gateway",
                })
            self.assertEqual(
                httplib.BAD_REQUEST, response.status_code, response.content)
            self.assertEquals({
                "__all__": ["This interface has no usable gateways."]
                }, json.loads(response.content))

    def test_set_default_gateway_requries_admin(self):
        node = factory.make_Node(interface=True)
        interface = node.get_boot_interface()
        uri = get_node_interface_uri(interface)
        response = self.client.post(uri, {
            "op": "set_default_gateway",
            })
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_set_default_gateway_409_when_not_ready_or_broken(self):
        self.become_admin()
        for status in (
                NODE_STATUS.NEW,
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.FAILED_COMMISSIONING,
                NODE_STATUS.MISSING,
                NODE_STATUS.RESERVED,
                NODE_STATUS.ALLOCATED,
                NODE_STATUS.DEPLOYING,
                NODE_STATUS.DEPLOYED,
                NODE_STATUS.RETIRED,
                NODE_STATUS.FAILED_DEPLOYMENT,
                NODE_STATUS.RELEASING,
                NODE_STATUS.FAILED_RELEASING,
                NODE_STATUS.DISK_ERASING,
                NODE_STATUS.FAILED_DISK_ERASING
        ):
            node = factory.make_Node(interface=True, status=status)
            interface = node.get_boot_interface()
            uri = get_node_interface_uri(interface)
            response = self.client.post(uri, {
                "op": "set_default_gateway",
                })
            self.assertEqual(
                httplib.CONFLICT, response.status_code, response.content)
