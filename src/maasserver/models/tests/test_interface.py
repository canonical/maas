# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Interface model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.http import Http404
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_PERMISSION,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.exceptions import (
    StaticIPAddressOutOfRange,
    StaticIPAddressUnavailable,
)
from maasserver.models import (
    Fabric,
    interface as interface_module,
    Space,
    StaticIPAddress,
    Subnet,
    VLAN,
)
from maasserver.models.interface import (
    BondInterface,
    Interface,
    PhysicalInterface,
    UnknownInterface,
    VLANInterface,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import (
    reload_object,
    reload_objects,
)
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from mock import (
    call,
    sentinel,
)
from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
)
from provisioningserver.utils.ipaddr import (
    get_first_and_last_usable_host_in_network,
)
from testtools import ExpectedException
from testtools.matchers import (
    Equals,
    MatchesDict,
    MatchesListwise,
    MatchesStructure,
)


class TestInterfaceManager(MAASServerTestCase):

    def test_get_queryset_returns_all_interface_types(self):
        physical = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[physical])
        vlan = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[bond])
        self.assertItemsEqual(
            [physical, bond, vlan], Interface.objects.all())

    def test_get_interface_or_404_returns_interface(self):
        node = factory.make_Node()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        user = factory.make_User()
        self.assertEqual(
            interface,
            Interface.objects.get_interface_or_404(
                node.system_id, interface.id, user, NODE_PERMISSION.VIEW))

    def test_get_interface_or_404_returns_interface_for_admin(self):
        node = factory.make_Node()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        user = factory.make_admin()
        self.assertEqual(
            interface,
            Interface.objects.get_interface_or_404(
                node.system_id, interface.id, user, NODE_PERMISSION.ADMIN))

    def test_get_interface_or_404_raises_Http404_when_invalid_id(self):
        node = factory.make_Node()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        user = factory.make_User()
        self.assertRaises(
            Http404,
            Interface.objects.get_interface_or_404,
            node.system_id, random.randint(100, 1000),
            user, NODE_PERMISSION.VIEW)

    def test_get_interface_or_404_raises_PermissionDenied_when_user(self):
        node = factory.make_Node()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        user = factory.make_User()
        self.assertRaises(
            PermissionDenied,
            Interface.objects.get_interface_or_404,
            node.system_id, interface.id,
            user, NODE_PERMISSION.ADMIN)


class TestInterfaceQueriesMixin(MAASServerTestCase):

    def test__filter_by_specifiers_default_matches_cidr_or_name(self):
        subnet1 = factory.make_Subnet()
        subnet2 = factory.make_Subnet()
        node1 = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet1)
        node2 = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet2)
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        iface3 = factory.make_Interface(
            iftype=INTERFACE_TYPE.BOND, parents=[iface2], name='bond0')
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "%s" % subnet1.cidr), [iface1])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "%s" % subnet2.cidr), [iface2])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                ["%s" % subnet1.cidr,
                 "%s" % subnet2.cidr], ), [iface1, iface2])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(iface1.name), [iface1])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(iface3.name), [iface3])

    def test__filter_by_specifiers_matches_fabric_class(self):
        fabric1 = factory.make_Fabric(class_type='10g')
        fabric2 = factory.make_Fabric(class_type='1g')
        vlan1 = factory.make_VLAN(vid=1, fabric=fabric1)
        vlan2 = factory.make_VLAN(vid=2, fabric=fabric2)
        iface1 = factory.make_Interface(vlan=vlan1)
        iface2 = factory.make_Interface(vlan=vlan2)
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "fabric_class:10g"), [iface1])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "fabric_class:1g"), [iface2])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                ["fabric_class:1g", "fabric_class:10g"]), [iface1, iface2])

    def test__filter_by_specifiers_matches_fabric(self):
        fabric1 = factory.make_Fabric(name="fabric1")
        fabric2 = factory.make_Fabric(name="fabric2")
        vlan1 = factory.make_VLAN(vid=1, fabric=fabric1)
        vlan2 = factory.make_VLAN(vid=2, fabric=fabric2)
        iface1 = factory.make_Interface(vlan=vlan1)
        iface2 = factory.make_Interface(vlan=vlan2)
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "fabric:fabric1"), [iface1])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "fabric:fabric2"), [iface2])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                ["fabric:fabric1", "fabric:fabric2"]), [iface1, iface2])

    def test__filter_by_specifiers_matches_interface_id(self):
        iface1 = factory.make_Interface()
        iface2 = factory.make_Interface()
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "id:%s" % iface1.id), [iface1])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "id:%s" % iface2.id), [iface2])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                ["id:%s" % iface1.id, "id:%s" % iface2.id]), [iface1, iface2])

    def test__filter_by_specifiers_matches_vid(self):
        iface1 = factory.make_Interface()
        iface2 = factory.make_Interface()
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "vid:%s" % iface1.vlan.vid), [iface1])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "vid:%s" % iface2.vlan.vid), [iface2])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                ["vid:%s" % iface1.vlan.vid, "vid:%s" % iface2.vlan.vid]),
            [iface1, iface2])

    def test__filter_by_specifiers_matches_subnet_specifier(self):
        subnet1 = factory.make_Subnet()
        subnet2 = factory.make_Subnet()
        node1 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet1)
        node2 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet2)
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "subnet:cidr:%s" % subnet1.cidr), [iface1])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "subnet:cidr:%s" % subnet2.cidr), [iface2])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                ["subnet:cidr:%s" % subnet1.cidr,
                 "subnet:cidr:%s" % subnet2.cidr], ), [iface1, iface2])

    def test__filter_by_specifiers_matches_subnet_cidr_alias(self):
        subnet1 = factory.make_Subnet()
        subnet2 = factory.make_Subnet()
        node1 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet1)
        node2 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet2)
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "subnet_cidr:%s" % subnet1.cidr), [iface1])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "subnet_cidr:%s" % subnet2.cidr), [iface2])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                ["subnet_cidr:%s" % subnet1.cidr,
                 "subnet_cidr:%s" % subnet2.cidr], ), [iface1, iface2])

    def test__filter_by_specifiers_matches_space(self):
        space1 = factory.make_Space()
        space2 = factory.make_Space()
        subnet1 = factory.make_Subnet(space=space1)
        subnet2 = factory.make_Subnet(space=space2)
        node1 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet1)
        node2 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet2)
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "space:%s" % space1.name), [iface1])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                "space:%s" % space2.name), [iface2])
        self.assertItemsEqual(
            Interface.objects.filter_by_specifiers(
                ["space:%s" % space1.name,
                 "space:%s" % space2.name], ), [iface1, iface2])

    def test__filter_by_specifiers_matches_type(self):
        physical = factory.make_Interface()
        bond = factory.make_Interface(
            iftype=INTERFACE_TYPE.BOND, parents=[physical])
        vlan = factory.make_Interface(
            iftype=INTERFACE_TYPE.VLAN, parents=[physical])
        unknown = factory.make_Interface(iftype=INTERFACE_TYPE.UNKNOWN)
        self.assertItemsEqual(Interface.objects.filter_by_specifiers(
            "type:physical"), [physical])
        self.assertItemsEqual(Interface.objects.filter_by_specifiers(
            "type:vlan"), [vlan])
        self.assertItemsEqual(Interface.objects.filter_by_specifiers(
            "type:bond"), [bond])
        self.assertItemsEqual(Interface.objects.filter_by_specifiers(
            "type:unknown"), [unknown])

    def test__filter_by_specifiers_matches_ip(self):
        subnet1 = factory.make_Subnet(cidr='10.0.0.0/24')
        subnet2 = factory.make_Subnet(cidr='10.0.1.0/24')
        iface1 = factory.make_Interface()
        iface2 = factory.make_Interface()
        factory.make_StaticIPAddress(
            ip='10.0.0.1', alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet1,
            interface=iface1)
        factory.make_StaticIPAddress(
            ip='10.0.1.1', alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet2,
            interface=iface2)
        self.assertItemsEqual(Interface.objects.filter_by_specifiers(
            "ip:10.0.0.1"), [iface1])
        self.assertItemsEqual(Interface.objects.filter_by_specifiers(
            "ip:10.0.1.1"), [iface2])

    def test__filter_by_specifiers_matches_unconfigured_mode(self):
        subnet1 = factory.make_Subnet(cidr='10.0.0.0/24')
        subnet2 = factory.make_Subnet(cidr='10.0.1.0/24')
        subnet3 = factory.make_Subnet(cidr='10.0.2.0/24')
        iface1 = factory.make_Interface()
        iface2 = factory.make_Interface()
        iface3 = factory.make_Interface()
        factory.make_StaticIPAddress(
            ip='', alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet1,
            interface=iface1)
        factory.make_StaticIPAddress(
            ip=None, alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet2,
            interface=iface2)
        factory.make_StaticIPAddress(
            ip='10.0.2.1', alloc_type=IPADDRESS_TYPE.AUTO, subnet=subnet3,
            interface=iface3)
        self.assertItemsEqual(
            [iface1, iface2],
            Interface.objects.filter_by_specifiers(
                "mode:unconfigured"))

    def test__get_matching_node_map(self):
        space1 = factory.make_Space()
        space2 = factory.make_Space()
        subnet1 = factory.make_Subnet(space=space1)
        subnet2 = factory.make_Subnet(space=space2)
        node1 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet1)
        node2 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet2)
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        nodes1, map1 = Interface.objects.get_matching_node_map(
            "space:%s" % space1.name)
        self.assertItemsEqual(nodes1, [node1.id])
        self.assertItemsEqual(map1, {node1.id: [iface1.id]})
        nodes2, map2 = Interface.objects.get_matching_node_map(
            "space:%s" % space2.name)
        self.assertItemsEqual(nodes2, [node2.id])
        self.assertItemsEqual(map2, {node2.id: [iface2.id]})
        nodes3, map3 = Interface.objects.get_matching_node_map(
            ["space:%s" % space1.name, "space:%s" % space2.name])
        self.assertItemsEqual(nodes3, [node1.id, node2.id])
        self.assertItemsEqual(map3, {
            node1.id: [iface1.id],
            node2.id: [iface2.id],
        })

    def test__get_matching_node_map_with_multiple_interfaces(self):
        space1 = factory.make_Space()
        space2 = factory.make_Space()
        subnet1 = factory.make_Subnet(space=space1)
        subnet2 = factory.make_Subnet(space=space2)
        node1 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet1)
        node2 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet2)
        iface1 = node1.get_boot_interface()
        iface2 = node2.get_boot_interface()
        iface3 = factory.make_Interface(node=node1)
        factory.make_StaticIPAddress(interface=iface3, subnet=subnet1)
        nodes1, map1 = Interface.objects.get_matching_node_map(
            "space:%s" % space1.name)
        self.assertItemsEqual(nodes1, [node1.id])
        self.assertItemsEqual(map1, {node1.id: [iface1.id, iface3.id]})
        nodes2, map2 = Interface.objects.get_matching_node_map(
            "space:%s" % space2.name)
        self.assertItemsEqual(nodes2, [node2.id])
        self.assertItemsEqual(map2, {node2.id: [iface2.id]})
        nodes3, map3 = Interface.objects.get_matching_node_map(
            ["space:%s" % space1.name, "space:%s" % space2.name])
        self.assertItemsEqual(nodes3, [node1.id, node2.id])
        self.assertItemsEqual(map3, {
            node1.id: [iface1.id, iface3.id],
            node2.id: [iface2.id],
        })


class InterfaceTest(MAASServerTestCase):

    def test_rejects_invalid_name(self):
        self.assertRaises(
            ValidationError,
            factory.make_Interface,
            INTERFACE_TYPE.PHYSICAL,
            name='invalid*name')

    def test_get_type_returns_None(self):
        self.assertIsNone(Interface.get_type())

    def test_creates_interface(self):
        name = factory.make_name('name')
        node = factory.make_Node()
        mac = factory.make_MAC()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name=name, node=node, mac_address=mac)
        self.assertThat(interface, MatchesStructure.byEquality(
            name=name, node=node, mac_address=mac,
            type=INTERFACE_TYPE.PHYSICAL))

    def test_unicode_representation_contains_essential_data(self):
        name = factory.make_name('name')
        node = factory.make_Node()
        mac = factory.make_MAC()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name=name, node=node, mac_address=mac)
        self.assertIn(mac.get_raw(), unicode(interface))
        self.assertIn(name, unicode(interface))

    def test_deletes_related_children(self):
        node = factory.make_Node()
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        nic2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[nic1, nic2])
        vlan = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[bond])
        nic1.delete()
        # Should not be deleted yet.
        self.assertIsNotNone(reload_object(bond), "Bond was deleted.")
        self.assertIsNotNone(reload_object(vlan), "VLAN was deleted.")
        nic2.delete()
        # Should now all be deleted.
        self.assertIsNone(reload_object(bond), "Bond was not deleted.")
        self.assertIsNone(reload_object(vlan), "VLAN was not deleted.")

    def test_get_links_returns_links_for_each_type(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        links = []
        dhcp_subnet = factory.make_Subnet()
        dhcp_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="",
            subnet=dhcp_subnet, interface=interface)
        links.append(
            MatchesDict({
                "id": Equals(dhcp_ip.id),
                "mode": Equals(INTERFACE_LINK_TYPE.DHCP),
                "subnet": Equals(dhcp_subnet),
            }))
        static_subnet = factory.make_Subnet()
        static_ip = factory.pick_ip_in_network(static_subnet.get_ipnetwork())
        sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=static_ip,
            subnet=static_subnet, interface=interface)
        links.append(
            MatchesDict({
                "id": Equals(sip.id),
                "mode": Equals(INTERFACE_LINK_TYPE.STATIC),
                "ip_address": Equals(static_ip),
                "subnet": Equals(static_subnet),
            }))
        link_subnet = factory.make_Subnet()
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=link_subnet, interface=interface)
        links.append(
            MatchesDict({
                "id": Equals(link_ip.id),
                "mode": Equals(INTERFACE_LINK_TYPE.LINK_UP),
                "subnet": Equals(link_subnet),
            }))
        self.assertThat(interface.get_links(), MatchesListwise(links))

    def test_get_discovered_returns_None_when_empty(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        self.assertIsNone(interface.get_discovered())

    def test_get_discovered_returns_discovered_address_for_ipv4_and_ipv6(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        discovered_ips = []
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        ip_v4 = factory.pick_ip_in_network(network_v4)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip_v4,
            subnet=subnet_v4, interface=interface)
        discovered_ips.append(
            MatchesDict({
                "ip_address": Equals(ip_v4),
                "subnet": Equals(subnet_v4),
            }))
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=unicode(network_v6.cidr))
        ip_v6 = factory.pick_ip_in_network(network_v6)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip_v6,
            subnet=subnet_v6, interface=interface)
        discovered_ips.append(
            MatchesDict({
                "ip_address": Equals(ip_v6),
                "subnet": Equals(subnet_v6),
            }))
        self.assertThat(
            interface.get_discovered(), MatchesListwise(discovered_ips))

    def test_delete_deletes_related_ip_addresses(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        discovered_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=interface)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, interface=interface)
        interface.delete()
        self.assertIsNone(reload_object(discovered_ip))
        self.assertIsNone(reload_object(static_ip))

    def test_delete_of_static_on_managed_will_remove_host_maps(self):
        mock_remove_host_maps = self.patch_autospec(
            interface_module, "remove_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet()
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip,
            subnet=subnet, interface=interface)
        interface.delete()
        self.assertIsNone(reload_object(static_ip))
        self.assertThat(
            mock_remove_host_maps,
            MockCalledOnceWith({
                nodegroup: {ip, interface.mac_address.get_raw()}
                }))

    def test_delete_of_discovered_will_remove_host_maps(self):
        mock_remove_host_maps = self.patch_autospec(
            interface_module, "remove_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet()
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip,
            subnet=subnet, interface=interface)
        interface.delete()
        self.assertIsNone(reload_object(static_ip))
        self.assertThat(
            mock_remove_host_maps,
            MockCalledOnceWith({
                nodegroup: {ip}
                }))

    def test_remove_gateway_link_on_node_ipv4(self):
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=unicode(network.cidr))
        ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network),
            subnet=subnet, interface=interface)
        node.gateway_link_ipv4 = ip
        node.save()
        reload_object(interface).ip_addresses.remove(ip)
        node = reload_object(node)
        self.assertIsNone(node.gateway_link_ipv4)

    def test_remove_gateway_link_on_node_ipv6(self):
        node = factory.make_Node()
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        network = factory.make_ipv6_network()
        subnet = factory.make_Subnet(cidr=unicode(network.cidr))
        ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_network(network),
            subnet=subnet, interface=interface)
        node.gateway_link_ipv6 = ip
        node.save()
        reload_object(interface).ip_addresses.remove(ip)
        node = reload_object(node)
        self.assertIsNone(node.gateway_link_ipv6)


class PhysicalInterfaceTest(MAASServerTestCase):

    def test_manager_returns_physical_interfaces(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            vlan=vlan, parents=[parent])
        self.assertItemsEqual(
            [parent], PhysicalInterface.objects.all())

    def test_get_node_returns_its_node(self):
        node = factory.make_Node()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=node)
        self.assertEqual(node, interface.get_node())

    def test_requires_node(self):
        interface = PhysicalInterface(
            name=factory.make_name("eth"),
            mac_address=factory.make_mac_address())
        error = self.assertRaises(ValidationError, interface.save)
        self.assertEquals({
            "node": ["This field cannot be blank."]
            }, error.error_dict)

    def test_requires_mac_address(self):
        interface = PhysicalInterface(
            name=factory.make_name("eth"),
            node=factory.make_Node())
        error = self.assertRaises(ValidationError, interface.save)
        self.assertEquals({
            "mac_address": ["This field cannot be blank."]
            }, error.error_dict)

    def test_mac_address_must_be_unique(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        bad_interface = PhysicalInterface(
            node=interface.node,
            mac_address=interface.mac_address,
            name=factory.make_name("eth"))
        error = self.assertRaises(ValidationError, bad_interface.save)
        self.assertEquals({
            "mac_address": [
                "This MAC address is already in use by %s." % (
                    interface.node.hostname)]
            }, error.error_dict)

    def test_cannot_have_parents(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        error = self.assertRaises(
            ValidationError, factory.make_Interface,
            INTERFACE_TYPE.PHYSICAL, node=parent.node, parents=[parent])
        self.assertEquals({
            "parents": ["A physical interface cannot have parents."]
            }, error.error_dict)

    def test_can_be_disabled(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface.enabled = False
        # Test is that this does not fail.
        interface.save()
        self.assertFalse(reload_object(interface).enabled)


class VLANInterfaceTest(MAASServerTestCase):

    def test_vlan_has_generated_name(self):
        name = factory.make_name('name')
        parent = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name=name)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            vlan=vlan, parents=[parent])
        self.assertEqual('%s.%d' % (parent.get_name(), vlan.vid),
                         interface.name)

    def test_generated_name_gets_update_if_vlan_id_changes(self):
        name = factory.make_name('name')
        parent = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name=name)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, vlan=vlan, parents=[parent])
        new_vlan = factory.make_VLAN()
        interface.vlan = new_vlan
        interface.save()
        self.assertEqual('%s.%d' % (parent.get_name(), new_vlan.vid),
                         interface.name)

    def test_manager_returns_vlan_interfaces(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, vlan=vlan, parents=[parent])
        self.assertItemsEqual(
            [interface], VLANInterface.objects.all())

    def test_get_node_returns_parent_node(self):
        node = factory.make_Node()
        parent = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=node)
        vlan = factory.make_VLAN()
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, vlan=vlan, parents=[parent])
        self.assertEqual(node, interface.get_node())

    def test_removed_if_underlying_interface_gets_removed(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[parent])
        parent.delete()
        self.assertIsNone(reload_object(interface))

    def test_can_only_have_one_parent(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        error = self.assertRaises(
            ValidationError, factory.make_Interface,
            INTERFACE_TYPE.VLAN, parents=[parent1, parent2])
        self.assertEquals({
            "parents": ["VLAN interface must have exactly one parent."]
            }, error.error_dict)

    def test_must_have_one_parent(self):
        error = self.assertRaises(
            ValidationError, factory.make_Interface,
            INTERFACE_TYPE.VLAN)
        self.assertEquals({
            "parents": ["VLAN interface must have exactly one parent."]
            }, error.error_dict)

    def test_parent_cannot_be_VLAN(self):
        physical = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[physical])
        error = self.assertRaises(
            ValidationError, factory.make_Interface,
            INTERFACE_TYPE.VLAN, parents=[vlan])
        self.assertEquals({
            "parents": [
                "VLAN interface can only be created on a physical "
                "or bond interface."],
            }, error.error_dict)

    def test_node_set_to_parent_node(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[parent])
        self.assertEquals(parent.node, interface.node)

    def test_mac_address_set_to_parent_mac_address(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[parent])
        self.assertEquals(parent.mac_address, interface.mac_address)

    def test_updating_parent_mac_address_updates_vlan_mac_address(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[parent])
        parent.mac_address = factory.make_mac_address()
        parent.save()
        interface = reload_object(interface)
        self.assertEquals(parent.mac_address, interface.mac_address)

    def test_disable_parent_disables_vlan_interface(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[parent])
        parent.enabled = False
        parent.save()
        self.assertFalse(interface.is_enabled())
        self.assertFalse(reload_object(interface).enabled)

    def test_enable_parent_enables_vlan_interface(self):
        parent = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[parent])
        parent.enabled = False
        parent.save()
        parent.enabled = True
        parent.save()
        self.assertTrue(interface.is_enabled())
        self.assertTrue(reload_object(interface).enabled)

    def test_disable_bond_parents_disables_vlan_interface(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=parent1.mac_address,
            parents=[parent1, parent2])
        interface = factory.make_Interface(
            INTERFACE_TYPE.VLAN, parents=[bond])
        parent1.enabled = False
        parent1.save()
        parent2.enabled = False
        parent2.save()
        self.assertFalse(interface.is_enabled())
        self.assertFalse(reload_object(interface).enabled)


class BondInterfaceTest(MAASServerTestCase):

    def test_manager_returns_bond_interfaces(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[parent1, parent2])
        self.assertItemsEqual(
            [interface], BondInterface.objects.all())

    def test_get_node_returns_parent_node(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[parent1, parent2])
        self.assertItemsEqual(
            [interface], BondInterface.objects.all())
        self.assertEqual(node, interface.get_node())

    def test_removed_if_underlying_interfaces_gets_removed(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[parent1, parent2])
        parent1.delete()
        parent2.delete()
        self.assertIsNone(reload_object(interface))

    def test_requires_mac_address(self):
        interface = BondInterface(
            name=factory.make_name("bond"), node=factory.make_Node())
        error = self.assertRaises(ValidationError, interface.save)
        self.assertEquals({
            "mac_address": ["This field cannot be blank."]
            }, error.error_dict)

    def test_parent_interfaces_must_belong_to_same_node(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        error = self.assertRaises(
            ValidationError, factory.make_Interface,
            INTERFACE_TYPE.BOND, parents=[parent1, parent2])
        self.assertEquals({
            "parents": ["Parent interfaces do not belong to the same node."]
            }, error.error_dict)

    def test_parent_interfaces_must_be_physical(self):
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan1 = factory.make_Interface(INTERFACE_TYPE.VLAN, parents=[parent1])
        error = self.assertRaises(
            ValidationError, factory.make_Interface,
            INTERFACE_TYPE.BOND, parents=[parent1, vlan1])
        self.assertEquals({
            "parents": ["Only physical interfaces can be bonded."]
            }, error.error_dict)

    def test_can_use_parents_mac_address(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        # Test is that no error is raised.
        factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=parent1.mac_address,
            parents=[parent1, parent2])

    def test_can_use_unique_mac_address(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        # Test is that no error is raised.
        factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=factory.make_mac_address(),
            parents=[parent1, parent2])

    def test_cannot_use_none_unique_mac_address(self):
        node = factory.make_Node()
        other_nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        # Test is that no error is raised.
        error = self.assertRaises(
            ValidationError, factory.make_Interface,
            INTERFACE_TYPE.BOND, mac_address=other_nic.mac_address,
            parents=[parent1, parent2])
        self.assertEquals({
            "mac_address": [
                "This MAC address is already in use by %s." % (
                    other_nic.node.hostname)]
            }, error.error_dict)

    def test_node_is_set_to_parents_node(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=factory.make_mac_address(),
            parents=[parent1, parent2])
        self.assertEquals(interface.node, parent1.node)

    def test_disable_one_parent_doesnt_disable_the_bond(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=factory.make_mac_address(),
            parents=[parent1, parent2])
        parent1.enabled = False
        parent1.save()
        self.assertTrue(interface.is_enabled())
        self.assertTrue(reload_object(interface).enabled)

    def test_disable_all_parents_disables_the_bond(self):
        node = factory.make_Node()
        parent1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        parent2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        interface = factory.make_Interface(
            INTERFACE_TYPE.BOND, mac_address=factory.make_mac_address(),
            parents=[parent1, parent2])
        parent1.enabled = False
        parent1.save()
        parent2.enabled = False
        parent2.save()
        self.assertFalse(interface.is_enabled())
        self.assertFalse(reload_object(interface).enabled)


class UnknownInterfaceTest(MAASServerTestCase):

    def test_manager_returns_unknown_interfaces(self):
        unknown = factory.make_Interface(INTERFACE_TYPE.UNKNOWN)
        self.assertItemsEqual(
            [unknown], UnknownInterface.objects.all())

    def test_get_node_returns_None(self):
        interface = factory.make_Interface(INTERFACE_TYPE.UNKNOWN)
        self.assertIsNone(interface.get_node())

    def test_doesnt_allow_node(self):
        interface = UnknownInterface(
            name="eth0",
            node=factory.make_Node(),
            mac_address=factory.make_mac_address())
        error = self.assertRaises(ValidationError, interface.save)
        self.assertEquals({
            "node": ["This field must be blank."]
            }, error.error_dict)

    def test_mac_address_must_be_unique(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        unknown = UnknownInterface(
            name="eth0", mac_address=interface.mac_address)
        error = self.assertRaises(ValidationError, unknown.save)
        self.assertEquals({
            "mac_address": [
                "This MAC address is already in use by %s." % (
                    interface.node.hostname)]
            }, error.error_dict)


class UpdateIpAddressesTest(MAASServerTestCase):

    def test__creates_missing_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network)
        address = unicode(network.ip)
        interface.update_ip_addresses([cidr])

        default_fabric = Fabric.objects.get_default_fabric()
        default_space = Space.objects.get_default_space()
        subnets = Subnet.objects.filter(
            cidr=unicode(network.cidr), vlan__fabric=default_fabric,
            space=default_space)
        self.assertEqual(1, len(subnets))
        self.assertEqual(1, interface.ip_addresses.count())
        self.assertThat(
            interface.ip_addresses.first(),
            MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnets[0],
                ip=address))

    def test__creates_discovered_ip_addresses(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = VLAN.objects.get_default_vlan()
        num_connections = 3
        cidr_list = [
            unicode(factory.make_ip4_or_6_network())
            for _ in range(num_connections)
        ]
        subnet_list = [
            factory.make_Subnet(cidr=cidr, vlan=vlan)
            for cidr in cidr_list
        ]

        interface.update_ip_addresses(cidr_list)

        self.assertEqual(num_connections, interface.ip_addresses.count())
        for i in range(num_connections):
            ip = interface.ip_addresses.order_by('id')[i]
            self.assertThat(ip, MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnet_list[i],
                ip=unicode(IPNetwork(cidr_list[i]).ip)))

    def test__deletes_old_discovered_ip_addresses_on_interface(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        # Create existing DISCOVERED IP address on the interface. These should
        # all be deleted.
        existing_discovered = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=interface)
            for i in range(3)
        ]
        interface.update_ip_addresses([])
        self.assertEqual(
            0, len(reload_objects(StaticIPAddress, existing_discovered)),
            "Discovered IP address should have been deleted.")

    def test__deletes_old_discovered_ip_addresses(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = VLAN.objects.get_default_vlan()
        num_connections = 3
        cidr_list = [
            unicode(factory.make_ip4_or_6_network())
            for _ in range(num_connections)
        ]
        subnet_list = [
            factory.make_Subnet(cidr=cidr, vlan=vlan)
            for cidr in cidr_list
        ]

        # Create existing DISCOVERED IP address with the same IP as those
        # that are going to be connected to the interface. These objects
        # should be deleted.
        existing_discovered = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DISCOVERED,
                ip=unicode(IPNetwork(cidr_list[i]).ip),
                subnet=subnet_list[i])
            for i in range(num_connections)
        ]

        interface.update_ip_addresses(cidr_list)

        self.assertEqual(
            0, len(reload_objects(StaticIPAddress, existing_discovered)),
            "Discovered IP address should have been deleted.")
        self.assertEqual(num_connections, interface.ip_addresses.count())
        for i in range(num_connections):
            ip = interface.ip_addresses.order_by('id')[i]
            self.assertThat(ip, MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnet_list[i],
                ip=unicode(IPNetwork(cidr_list[i]).ip)))

    def test__deletes_old_discovered_ip_addresses_with_unknown_nics(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = VLAN.objects.get_default_vlan()
        num_connections = 3
        cidr_list = [
            unicode(factory.make_ip4_or_6_network())
            for _ in range(num_connections)
        ]
        subnet_list = [
            factory.make_Subnet(cidr=cidr, vlan=vlan)
            for cidr in cidr_list
        ]

        # Create existing DISCOVERED IP address with the same IP as those
        # that are going to be connected to the interface. Each IP address
        # is linked to an UnknownInterface. The interfaces and the static IP
        # address should be deleted.
        existing_nics = [
            UnknownInterface.objects.create(
                name="eth0", mac_address=factory.make_mac_address(),
                vlan=subnet_list[i].vlan)
            for i in range(num_connections)
        ]
        existing_discovered = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DISCOVERED,
                ip=unicode(IPNetwork(cidr_list[i]).ip),
                subnet=subnet_list[i], interface=existing_nics[i])
            for i in range(num_connections)
        ]

        interface.update_ip_addresses(cidr_list)

        self.assertEqual(
            0, len(reload_objects(StaticIPAddress, existing_discovered)),
            "Discovered IP address should have been deleted.")
        self.assertEqual(
            0, len(reload_objects(UnknownInterface, existing_nics)),
            "Unknown interfaces should have been deleted.")
        self.assertEqual(num_connections, interface.ip_addresses.count())
        for i in range(num_connections):
            ip = interface.ip_addresses.order_by('id')[i]
            self.assertThat(ip, MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnet_list[i],
                ip=unicode(IPNetwork(cidr_list[i]).ip)))

    def test__deletes_old_sticky_ip_addresses_not_linked(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        vlan = VLAN.objects.get_default_vlan()
        num_connections = 3
        cidr_list = [
            unicode(factory.make_ip4_or_6_network())
            for _ in range(num_connections)
        ]
        subnet_list = [
            factory.make_Subnet(cidr=cidr, vlan=vlan)
            for cidr in cidr_list
        ]

        # Create existing DISCOVERED IP address with the same IP as those
        # that are going to be connected to the interface. These objects
        # should be deleted.
        existing_discovered = [
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip=unicode(IPNetwork(cidr_list[i]).ip),
                subnet=subnet_list[i])
            for i in range(num_connections)
        ]

        interface.update_ip_addresses(cidr_list)

        self.assertEqual(
            0, len(reload_objects(StaticIPAddress, existing_discovered)),
            "Sticky IP address should have been deleted.")
        self.assertEqual(num_connections, interface.ip_addresses.count())
        for i in range(num_connections):
            ip = interface.ip_addresses.order_by('id')[i]
            self.assertThat(ip, MatchesStructure.byEquality(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet=subnet_list[i],
                ip=unicode(IPNetwork(cidr_list[i]).ip)))

    def test__deletes_old_ip_address_on_managed_subnet_with_log(self):
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network)
        address = unicode(network.ip)
        vlan = VLAN.objects.get_default_vlan()
        subnet = factory.make_Subnet(cidr=cidr, vlan=vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        other_interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=address,
            subnet=subnet, interface=other_interface)
        maaslog = self.patch_autospec(interface_module, "maaslog")

        # Update that ip address on another interface. Which will log the
        # error message and delete the IP address.
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface.update_ip_addresses([cidr])

        self.assertThat(
            maaslog.warn,
            MockCalledOnceWith(
                "%s IP address (%s)%s was deleted because "
                "it was handed out by the MAAS DHCP server "
                "from the dynamic range.",
                ip.get_log_name_for_alloc_type(),
                address, " on " + other_interface.node.fqdn))

    def test__deletes_old_ip_address_on_unmanaged_subnet_with_log(self):
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network)
        address = unicode(network.ip)
        vlan = VLAN.objects.get_default_vlan()
        subnet = factory.make_Subnet(cidr=cidr, vlan=vlan)
        other_interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=address,
            subnet=subnet, interface=other_interface)
        maaslog = self.patch_autospec(interface_module, "maaslog")

        # Update that ip address on another interface. Which will log the
        # error message and delete the IP address.
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface.update_ip_addresses([cidr])

        self.assertThat(
            maaslog.warn,
            MockCalledOnceWith(
                "%s IP address (%s)%s was deleted because "
                "it was handed out by an external DHCP "
                "server.",
                ip.get_log_name_for_alloc_type(),
                address, " on " + other_interface.node.fqdn))


class TestLinkSubnet(MAASServerTestCase):
    """Tests for `Interface.link_subnet`."""

    def test__AUTO_creates_link_to_AUTO_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        auto_subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=auto_subnet)
        interface.link_subnet(INTERFACE_LINK_TYPE.AUTO, auto_subnet)
        interface = reload_object(interface)
        auto_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.AUTO)
        self.assertEquals(auto_subnet, auto_ip.subnet)

    def test__DHCP_creates_link_to_DHCP_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        dhcp_subnet = factory.make_Subnet(vlan=interface.vlan)
        interface.link_subnet(INTERFACE_LINK_TYPE.DHCP, dhcp_subnet)
        interface = reload_object(interface)
        dhcp_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.DHCP)
        self.assertEquals(dhcp_subnet, dhcp_ip.subnet)

    def test__DHCP_creates_link_to_DHCP_without_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface.link_subnet(INTERFACE_LINK_TYPE.DHCP, None)
        interface = reload_object(interface)
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DHCP)))

    def test__STATIC_not_allowed_if_ip_address_not_in_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network.cidr))
        ip_not_in_subnet = factory.make_ipv6_address()
        error = self.assertRaises(
            StaticIPAddressOutOfRange, interface.link_subnet,
            INTERFACE_LINK_TYPE.STATIC, subnet, ip_address=ip_not_in_subnet)
        self.assertEquals(
            "IP address is not in the given subnet '%s'." % subnet,
            error.message)

    def test__STATIC_not_allowed_if_ip_address_in_dynamic_range(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        ip_in_dynamic = IPAddress(ngi.get_dynamic_ip_range().first)
        error = self.assertRaises(
            StaticIPAddressOutOfRange, interface.link_subnet,
            INTERFACE_LINK_TYPE.STATIC, subnet, ip_address=ip_in_dynamic)
        self.assertEquals(
            "IP address is inside a managed dynamic range %s-%s." % (
                ngi.ip_range_low, ngi.ip_range_high),
            error.message)

    def test__STATIC_sets_ip_in_no_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        ip = factory.make_ip_address()
        interface.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, None, ip_address=ip)
        interface = reload_object(interface)
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(
                    alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=None)))

    def test__STATIC_sets_ip_in_unmanaged_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        interface.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, subnet, ip_address=ip)
        interface = reload_object(interface)
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(
                    alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet)))

    def test__STATIC_sets_ip_in_managed_subnet(self):
        self.patch_autospec(interface_module, "update_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        ip_in_static = IPAddress(ngi.get_static_ip_range().first)
        interface.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, subnet, ip_address=ip_in_static)
        interface = reload_object(interface)
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(
                    alloc_type=IPADDRESS_TYPE.STICKY, ip="%s" % ip_in_static,
                    subnet=subnet)))

    def test__STATIC_picks_ip_in_unmanaged_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        interface.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, subnet)
        interface = reload_object(interface)
        ip_address = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet))
        self.assertIsNotNone(ip_address)
        self.assertIn(IPAddress(ip_address.ip), subnet.get_ipnetwork())

    def test__STATIC_picks_ip_in_managed_subnet(self):
        self.patch_autospec(interface_module, "update_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        interface.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, subnet)
        interface = reload_object(interface)
        ip_address = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet))
        self.assertIsNotNone(ip_address)
        self.assertIn(IPAddress(ip_address.ip), ngi.get_static_ip_range())

    def test__STATIC_calls_update_host_maps(self):
        mock_update_host_maps = self.patch_autospec(
            interface_module, "update_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        interface.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, subnet)
        interface = reload_object(interface)
        ip_address = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet))
        self.assertIsNotNone(ip_address)
        self.assertThat(
            mock_update_host_maps,
            MockCalledOnceWith({
                ngi.nodegroup: {
                    ip_address.ip: interface.mac_address.get_raw(),
                }}))

    def test__STATIC_calls_dns_update_zones(self):
        from maasserver.dns import config
        self.patch_autospec(interface_module, "update_host_maps")
        mock_dns_update_zones = self.patch_autospec(
            config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        interface.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, subnet)
        interface = reload_object(interface)
        ip_address = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet))
        self.assertIsNotNone(ip_address)
        self.assertThat(
            mock_dns_update_zones,
            MockCalledOnceWith({nodegroup, interface.node.nodegroup}))

    def test__STATIC_doesnt_call_update_host_maps_when_allocations_exist(self):
        mock_update_host_maps = self.patch_autospec(
            interface_module, "update_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=unicode(IPAddress(subnet.get_ipnetwork().last - 1)),
            subnet=subnet, interface=interface)
        interface.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, subnet)
        self.assertThat(mock_update_host_maps, MockNotCalled())

    def test__LINK_UP_creates_link_STICKY_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        link_subnet = factory.make_Subnet(vlan=interface.vlan)
        interface.link_subnet(
            INTERFACE_LINK_TYPE.LINK_UP, link_subnet)
        interface = reload_object(interface)
        link_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.STICKY)
        self.assertIsNone(link_ip.ip)
        self.assertEquals(link_subnet, link_ip.subnet)

    def test__LINK_UP_creates_link_STICKY_without_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface.link_subnet(
            INTERFACE_LINK_TYPE.LINK_UP, None)
        interface = reload_object(interface)
        link_ip = get_one(
            interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.STICKY))
        self.assertIsNotNone(link_ip)
        self.assertIsNone(link_ip.ip)


class TestForceAutoOrDHCPLink(MAASServerTestCase):
    """Tests for `Interface.force_auto_or_dhcp_link`."""

    def test__sets_to_AUTO_on_managed_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = interface.force_auto_or_dhcp_link()
        self.assertEquals(IPADDRESS_TYPE.AUTO, static_ip.alloc_type)
        self.assertEquals(subnet, static_ip.subnet)

    def test__sets_to_DHCP(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        static_ip = interface.force_auto_or_dhcp_link()
        self.assertEquals(IPADDRESS_TYPE.DHCP, static_ip.alloc_type)
        self.assertIsNone(static_ip.subnet)


class TestEnsureLinkUp(MAASServerTestCase):
    """Tests for `Interface.ensure_link_up`."""

    def test__does_nothing_if_has_link(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        interface.link_subnet(INTERFACE_LINK_TYPE.DHCP, subnet)
        interface.ensure_link_up()
        interface = reload_object(interface)
        self.assertEquals(
            1, interface.ip_addresses.count(),
            "Should only have one IP address assigned.")

    def test__creates_link_up_to_discovered_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            subnet=subnet, interface=interface)
        interface.ensure_link_up()
        link_ip = interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY).first()
        self.assertIsNone(link_ip.ip)
        self.assertEquals(subnet, link_ip.subnet)

    def test__creates_link_up_to_no_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface.ensure_link_up()
        link_ip = interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.STICKY).first()
        self.assertIsNone(link_ip.ip)
        self.assertIsNone(link_ip.subnet)


class TestUnlinkIPAddress(MAASServerTestCase):
    """Tests for `Interface.unlink_ip_address`."""

    def test__doesnt_call_ensure_link_up_if_clearing_config(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        auto_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        mock_ensure_link_up = self.patch_autospec(interface, "ensure_link_up")
        interface.unlink_ip_address(auto_ip, clearing_config=True)
        self.assertIsNone(reload_object(auto_ip))
        self.assertThat(mock_ensure_link_up, MockNotCalled())


class TestUnlinkSubnet(MAASServerTestCase):
    """Tests for `Interface.unlink_subnet`."""

    def test__AUTO_deletes_link(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        auto_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        interface.unlink_subnet_by_id(auto_ip.id)
        self.assertIsNone(reload_object(auto_ip))

    def test__DHCP_deletes_link_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        dhcp_subnet = factory.make_Subnet(vlan=interface.vlan)
        interface.link_subnet(INTERFACE_LINK_TYPE.DHCP, dhcp_subnet)
        interface = reload_object(interface)
        dhcp_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.DHCP)
        interface.unlink_subnet_by_id(dhcp_ip.id)
        self.assertIsNone(reload_object(dhcp_ip))

    def test__STATIC_deletes_link_in_no_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        ip = factory.make_ip_address()
        interface.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, None, ip_address=ip)
        interface = reload_object(interface)
        static_ip = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=None))
        interface.unlink_subnet_by_id(static_ip.id)
        self.assertIsNone(reload_object(static_ip))

    def test__STATIC_deletes_link_in_unmanaged_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        interface.link_subnet(
            INTERFACE_LINK_TYPE.STATIC, subnet, ip_address=ip)
        interface = reload_object(interface)
        static_ip = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet))
        interface.unlink_subnet_by_id(static_ip.id)
        self.assertIsNone(reload_object(static_ip))

    def test__STATIC_deletes_link_in_managed_subnet(self):
        mock_remove_host_maps = self.patch_autospec(
            interface_module, "remove_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip,
            subnet=subnet, interface=interface)
        interface.unlink_subnet_by_id(static_ip.id)
        self.assertIsNone(reload_object(static_ip))
        self.assertThat(mock_remove_host_maps, MockCalledOnceWith({
            nodegroup: {static_ip.ip, interface.mac_address.get_raw()},
            }))

    def test__STATIC_deletes_link_in_managed_subnet_calls_update_on_next(self):
        mock_remove_host_maps = self.patch_autospec(
            interface_module, "remove_host_maps")
        mock_update_host_maps = self.patch_autospec(
            interface_module, "update_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        ip_one = factory.pick_ip_in_network(subnet.get_ipnetwork())
        ip_two = factory.pick_ip_in_network(
            subnet.get_ipnetwork(), but_not=[ip_one])
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_one,
            subnet=subnet, interface=interface)
        next_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip_two,
            subnet=subnet, interface=interface)
        interface.unlink_subnet_by_id(static_ip.id)
        self.assertIsNone(reload_object(static_ip))
        self.assertThat(mock_remove_host_maps, MockCalledOnceWith({
            nodegroup: {static_ip.ip, interface.mac_address.get_raw()},
            }))
        self.assertThat(mock_update_host_maps, MockCalledOnceWith({
            nodegroup: {next_ip.ip: interface.mac_address.get_raw()},
            }))

    def test__STATIC_calls_dns_update_zones(self):
        from maasserver.dns import config
        self.patch_autospec(interface_module, "remove_host_maps")
        self.patch_autospec(interface_module, "update_host_maps")
        mock_dns_update_zones = self.patch_autospec(
            config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip,
            subnet=subnet, interface=interface)
        interface.unlink_subnet_by_id(static_ip.id)
        self.assertThat(
            mock_dns_update_zones,
            MockCalledOnceWith({nodegroup, interface.node.nodegroup}))

    def test__LINK_UP_deletes_link(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=subnet, interface=interface)
        interface.unlink_subnet_by_id(link_ip.id)
        self.assertIsNone(reload_object(link_ip))

    def test__always_has_LINK_UP(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=subnet, interface=interface)
        interface.unlink_subnet_by_id(link_ip.id)
        self.assertIsNone(reload_object(link_ip))
        self.assertIsNotNone(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=None).first())


class TestUpdateIPAddress(MAASServerTestCase):
    """Tests for `Interface.update_ip_address`."""

    def test__switch_dhcp_to_auto(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="",
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        new_subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.AUTO, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.AUTO, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNone(static_ip.ip)

    def test__switch_dhcp_to_link_up(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="",
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        new_subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.LINK_UP, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.STICKY, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNone(static_ip.ip)

    def test__switch_dhcp_to_static(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        network_v4 = factory.make_ipv4_network(slash=24)
        subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v4.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="",
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        network_v6 = factory.make_ipv6_network(slash=24)
        new_subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v6.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=new_subnet)
        mock_update_host_maps = self.patch_autospec(
            interface, "_update_host_maps")
        mock_update_dns_zones = self.patch_autospec(
            interface, "_update_dns_zones")
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.STATIC, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.STICKY, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNotNone(static_ip.ip)
        self.assertThat(
            mock_update_host_maps, MockCalledOnceWith(nodegroup, static_ip))
        self.assertThat(
            mock_update_dns_zones, MockCalledOnceWith([nodegroup]))

    def test__switch_auto_to_dhcp(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        new_subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.DHCP, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.DHCP, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNone(static_ip.ip)

    def test__switch_auto_to_link_up(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        new_subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.LINK_UP, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.STICKY, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNone(static_ip.ip)

    def test__switch_auto_to_static(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        network_v4 = factory.make_ipv4_network(slash=24)
        subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v4.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        network_v6 = factory.make_ipv6_network(slash=24)
        new_subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v6.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=new_subnet)
        mock_update_host_maps = self.patch_autospec(
            interface, "_update_host_maps")
        mock_update_dns_zones = self.patch_autospec(
            interface, "_update_dns_zones")
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.STATIC, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.STICKY, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNotNone(static_ip.ip)
        self.assertThat(
            mock_update_host_maps, MockCalledOnceWith(nodegroup, static_ip))
        self.assertThat(
            mock_update_dns_zones, MockCalledOnceWith([nodegroup]))

    def test__switch_link_up_to_auto(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        new_subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.AUTO, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.AUTO, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNone(static_ip.ip)

    def test__switch_link_up_to_dhcp(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        new_subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.DHCP, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.DHCP, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNone(static_ip.ip)

    def test__switch_link_up_to_static(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        network_v4 = factory.make_ipv4_network(slash=24)
        subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v4.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        network_v6 = factory.make_ipv6_network(slash=24)
        new_subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v6.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=new_subnet)
        mock_update_host_maps = self.patch_autospec(
            interface, "_update_host_maps")
        mock_update_dns_zones = self.patch_autospec(
            interface, "_update_dns_zones")
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.STATIC, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.STICKY, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNotNone(static_ip.ip)
        self.assertThat(
            mock_update_host_maps, MockCalledOnceWith(nodegroup, static_ip))
        self.assertThat(
            mock_update_dns_zones, MockCalledOnceWith([nodegroup]))

    def test__switch_static_to_dhcp(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_static_range(ngi),
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        new_subnet = factory.make_Subnet(vlan=interface.vlan)
        mock_remove_host_maps = self.patch_autospec(
            interface, "_remove_host_maps")
        mock_update_dns_zones = self.patch_autospec(
            interface, "_update_dns_zones")
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.DHCP, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.DHCP, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNone(static_ip.ip)
        self.assertThat(
            mock_remove_host_maps, MockCalledOnceWith(nodegroup, static_ip))
        self.assertThat(
            mock_update_dns_zones, MockCalledOnceWith([nodegroup]))

    def test__switch_static_to_auto(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_static_range(ngi),
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        new_subnet = factory.make_Subnet(vlan=interface.vlan)
        mock_remove_host_maps = self.patch_autospec(
            interface, "_remove_host_maps")
        mock_update_dns_zones = self.patch_autospec(
            interface, "_update_dns_zones")
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.AUTO, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.AUTO, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNone(static_ip.ip)
        self.assertThat(
            mock_remove_host_maps, MockCalledOnceWith(nodegroup, static_ip))
        self.assertThat(
            mock_update_dns_zones, MockCalledOnceWith([nodegroup]))

    def test__switch_static_to_link_up(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_static_range(ngi),
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        new_subnet = factory.make_Subnet(vlan=interface.vlan)
        mock_remove_host_maps = self.patch_autospec(
            interface, "_remove_host_maps")
        mock_update_dns_zones = self.patch_autospec(
            interface, "_update_dns_zones")
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.LINK_UP, new_subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.STICKY, static_ip.alloc_type)
        self.assertEquals(new_subnet, static_ip.subnet)
        self.assertIsNone(static_ip.ip)
        self.assertThat(
            mock_remove_host_maps, MockCalledOnceWith(nodegroup, static_ip))
        self.assertThat(
            mock_update_dns_zones, MockCalledOnceWith([nodegroup]))

    def test__switch_static_to_same_subnet_does_nothing(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_static_range(ngi),
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        static_ip_address = static_ip.ip
        mock_remove_host_maps = self.patch_autospec(
            interface, "_remove_host_maps")
        mock_update_host_maps = self.patch_autospec(
            interface, "_update_host_maps")
        mock_update_dns_zones = self.patch_autospec(
            interface, "_update_dns_zones")
        static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.STATIC, subnet)
        self.assertEquals(static_id, static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.STICKY, static_ip.alloc_type)
        self.assertEquals(subnet, static_ip.subnet)
        self.assertEquals(static_ip_address, static_ip.ip)
        self.assertThat(mock_remove_host_maps, MockNotCalled())
        self.assertThat(mock_update_host_maps, MockNotCalled())
        self.assertThat(mock_update_dns_zones, MockNotCalled())

    def test__switch_static_to_already_used_ip_address(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_static_range(ngi),
            subnet=subnet, interface=interface)
        other_interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        used_ip_address = factory.pick_ip_in_static_range(
            ngi, but_not=[static_ip.ip])
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=used_ip_address,
            subnet=subnet, interface=other_interface)
        with ExpectedException(StaticIPAddressUnavailable):
            interface.update_ip_address(
                static_ip, INTERFACE_LINK_TYPE.STATIC, subnet,
                ip_address=used_ip_address)

    def test__switch_static_to_same_subnet_with_different_ip(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        network = factory.make_ipv4_network(slash=24)
        subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network.cidr))
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_static_range(ngi),
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        static_ip_address = static_ip.ip
        new_ip_address = factory.pick_ip_in_static_range(
            ngi, but_not=[static_ip_address])
        mock_remove_host_maps = self.patch_autospec(
            interface, "_remove_host_maps")
        mock_update_host_maps = self.patch_autospec(
            interface, "_update_host_maps")
        mock_update_dns_zones = self.patch_autospec(
            interface, "_update_dns_zones")
        new_static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.STATIC, subnet,
            ip_address=new_ip_address)
        self.assertEquals(static_id, new_static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.STICKY, new_static_ip.alloc_type)
        self.assertEquals(subnet, new_static_ip.subnet)
        self.assertEquals(new_ip_address, new_static_ip.ip)
        # The remove actual loads the IP address from the database so it
        # is not the same object. We just need to check that the IP's match.
        self.assertEquals(nodegroup, mock_remove_host_maps.call_args[0][0])
        self.assertEquals(
            static_ip_address, mock_remove_host_maps.call_args[0][1].ip)
        self.assertThat(
            mock_update_host_maps,
            MockCalledOnceWith(nodegroup, new_static_ip))
        self.assertThat(
            mock_update_dns_zones, MockCalledOnceWith([nodegroup]))

    def test__switch_static_to_another_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup_v4 = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        network_v4 = factory.make_ipv4_network(slash=24)
        subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v4.cidr))
        ngi = factory.make_NodeGroupInterface(
            nodegroup_v4, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_static_range(ngi),
            subnet=subnet, interface=interface)
        other_static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_static_range(ngi, but_not=[static_ip.ip]),
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        nodegroup_v6 = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        network_v6 = factory.make_ipv6_network(slash=24)
        new_subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v6.cidr))
        new_ngi = factory.make_NodeGroupInterface(
            nodegroup_v6, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=new_subnet)
        new_subnet_static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_static_range(new_ngi),
            subnet=new_subnet, interface=interface)
        mock_remove_host_maps = self.patch_autospec(
            interface, "_remove_host_maps")
        mock_update_host_maps = self.patch_autospec(
            interface, "_update_host_maps")
        mock_update_dns_zones = self.patch_autospec(
            interface, "_update_dns_zones")
        new_static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.STATIC, new_subnet)
        self.assertEquals(static_id, new_static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.STICKY, new_static_ip.alloc_type)
        self.assertEquals(new_subnet, new_static_ip.subnet)
        self.assertIsNotNone(new_static_ip.ip)
        self.assertThat(
            mock_remove_host_maps,
            MockCallsMatch(
                call(nodegroup_v6, new_subnet_static_ip),
                call(nodegroup_v4, static_ip),
            ))
        self.assertThat(
            mock_update_host_maps,
            MockCallsMatch(
                call(nodegroup_v4, other_static_ip),
                call(nodegroup_v6, new_static_ip),
            ))
        self.assertThat(
            mock_update_dns_zones,
            MockCallsMatch(
                call([nodegroup_v4]),
                call([nodegroup_v6]),
            ))

    def test__switch_static_to_another_subnet_with_ip_address(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        nodegroup_v4 = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        network_v4 = factory.make_ipv4_network(slash=24)
        subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v4.cidr))
        ngi = factory.make_NodeGroupInterface(
            nodegroup_v4, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip=factory.pick_ip_in_static_range(ngi),
            subnet=subnet, interface=interface)
        static_id = static_ip.id
        nodegroup_v6 = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        network_v6 = factory.make_ipv6_network(slash=24)
        new_subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v6.cidr))
        new_ngi = factory.make_NodeGroupInterface(
            nodegroup_v6, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=new_subnet)
        new_ip_address = factory.pick_ip_in_static_range(new_ngi)
        mock_remove_host_maps = self.patch_autospec(
            interface, "_remove_host_maps")
        mock_update_host_maps = self.patch_autospec(
            interface, "_update_host_maps")
        mock_update_dns_zones = self.patch_autospec(
            interface, "_update_dns_zones")
        new_static_ip = interface.update_ip_address(
            static_ip, INTERFACE_LINK_TYPE.STATIC, new_subnet,
            ip_address=new_ip_address)
        self.assertEquals(static_id, new_static_ip.id)
        self.assertEquals(IPADDRESS_TYPE.STICKY, new_static_ip.alloc_type)
        self.assertEquals(new_subnet, new_static_ip.subnet)
        self.assertEquals(new_ip_address, new_static_ip.ip)
        self.assertThat(
            mock_remove_host_maps,
            MockCalledOnceWith(nodegroup_v4, static_ip))
        self.assertThat(
            mock_update_host_maps,
            MockCalledOnceWith(nodegroup_v6, new_static_ip))
        self.assertThat(
            mock_update_dns_zones,
            MockCallsMatch(
                call([nodegroup_v4]),
                call([nodegroup_v6]),
            ))


class TestUpdateLinkById(MAASServerTestCase):
    """Tests for `Interface.update_link_by_id`."""

    def test__calls_update_ip_address_with_ip_address(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="",
            subnet=subnet, interface=interface)
        mock_update_ip_address = self.patch_autospec(
            interface, "update_ip_address")
        interface.update_link_by_id(
            static_ip.id, INTERFACE_LINK_TYPE.AUTO, subnet)
        self.expectThat(mock_update_ip_address, MockCalledOnceWith(
            static_ip, INTERFACE_LINK_TYPE.AUTO, subnet, ip_address=None))


class TestClaimAutoIPs(MAASServerTestCase):
    """Tests for `Interface.claim_auto_ips`."""

    def test__claims_all_auto_ip_addresses(self):
        from maasserver.dns import config
        self.patch_autospec(interface_module, "update_host_maps")
        self.patch_autospec(config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        for _ in range(3):
            subnet = factory.make_Subnet(vlan=interface.vlan)
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO, ip="",
                subnet=subnet, interface=interface)
        observed = interface.claim_auto_ips()

        # Should now have 3 AUTO with IP addresses assigned.
        interface = reload_object(interface)
        assigned_addresses = interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO)
        assigned_addresses = [
            ip
            for ip in assigned_addresses
            if ip.ip
        ]
        self.assertEquals(
            3, len(assigned_addresses),
            "Should have 3 AUTO IP addresses with an IP address assigned.")
        self.assertItemsEqual(assigned_addresses, observed)

    def test__claims_all_missing_assigned_auto_ip_addresses(self):
        from maasserver.dns import config
        self.patch_autospec(interface_module, "update_host_maps")
        self.patch_autospec(config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        for _ in range(3):
            subnet = factory.make_Subnet(vlan=interface.vlan)
            ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO, ip=ip,
                subnet=subnet, interface=interface)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        observed = interface.claim_auto_ips()
        self.assertEquals(
            1, len(observed),
            "Should have 1 AUTO IP addresses with an IP address assigned.")
        self.assertEquals(subnet, observed[0].subnet)
        self.assertTrue(
            IPAddress(observed[0].ip) in observed[0].subnet.get_ipnetwork(),
            "Assigned IP address should be inside the subnet network.")

    def test__claims_ip_address_in_static_ip_range(self):
        from maasserver.dns import config
        self.patch_autospec(interface_module, "update_host_maps")
        self.patch_autospec(config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        observed = interface.claim_auto_ips()
        self.assertEquals(
            1, len(observed),
            "Should have 1 AUTO IP addresses with an IP address assigned.")
        self.assertEquals(subnet, observed[0].subnet)
        self.assertTrue(
            IPAddress(observed[0].ip) in (
                IPRange(ngi.static_ip_range_low, ngi.static_ip_range_low)),
            "Assigned IP address should be inside the static range "
            "on the cluster.")

    def test__calls_update_host_maps(self):
        from maasserver.dns import config
        mock_update_host_maps = self.patch_autospec(
            interface_module, "update_host_maps")
        self.patch_autospec(config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        observed = interface.claim_auto_ips()
        self.assertThat(
            mock_update_host_maps, MockCalledOnceWith({
                nodegroup: {observed[0].ip: interface.mac_address.get_raw()}
                }))

    def test__calls_update_host_maps_per_address_family(self):
        from maasserver.dns import config
        mock_update_host_maps = self.patch_autospec(
            interface_module, "update_host_maps")
        self.patch_autospec(config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v4.cidr))
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network_v6.cidr))
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            subnet=subnet_v4)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            subnet=subnet_v6)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet_v4, interface=interface)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet_v6, interface=interface)
        observed = interface.claim_auto_ips()
        self.assertThat(
            mock_update_host_maps, MockCallsMatch(
                call({
                    nodegroup: {
                        observed[0].ip: interface.mac_address.get_raw(),
                    }
                }),
                call({
                    nodegroup: {
                        observed[1].ip: interface.mac_address.get_raw(),
                    }
                })))

    def test__calls_dns_update_zones(self):
        from maasserver.dns import config
        self.patch_autospec(interface_module, "update_host_maps")
        mock_dns_update_zones = self.patch_autospec(
            config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        interface.claim_auto_ips()
        self.assertThat(
            mock_dns_update_zones,
            MockCalledOnceWith({nodegroup, interface.node.nodegroup}))

    def test__excludes_ip_addresses_in_exclude_addresses(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        exclude = get_first_and_last_usable_host_in_network(
            subnet.get_ipnetwork())[0]
        interface.claim_auto_ips(exclude_addresses=set([unicode(exclude)]))
        auto_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.AUTO)
        self.assertEquals(IPAddress(exclude) + 1, IPAddress(auto_ip.ip))

    def test__can_acquire_multiple_address_from_the_same_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip="",
            subnet=subnet, interface=interface)
        interface.claim_auto_ips()
        auto_ips = interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO).order_by('id')
        self.assertEquals(
            IPAddress(auto_ips[0].ip) + 1, IPAddress(auto_ips[1].ip))


class TestReleaseAutoIPs(MAASServerTestCase):
    """Tests for `Interface.release_auto_ips`."""

    def test__clears_all_auto_ips_with_ips(self):
        from maasserver.dns import config
        self.patch_autospec(interface_module, "remove_host_maps")
        self.patch_autospec(interface_module, "update_host_maps")
        self.patch_autospec(config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        for _ in range(3):
            subnet = factory.make_Subnet(vlan=interface.vlan)
            ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO, ip=ip,
                subnet=subnet, interface=interface)
        observed = interface.release_auto_ips()

        # Should now have 3 AUTO with no IP addresses assigned.
        interface = reload_object(interface)
        releases_addresses = interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.AUTO)
        releases_addresses = [
            rip
            for rip in releases_addresses
            if not rip.ip
        ]
        self.assertEquals(
            3, len(releases_addresses),
            "Should have 3 AUTO IP addresses with no IP address assigned.")
        self.assertItemsEqual(releases_addresses, observed)

    def test__clears_only_auto_ips_with_ips(self):
        from maasserver.dns import config
        self.patch_autospec(interface_module, "remove_host_maps")
        self.patch_autospec(interface_module, "update_host_maps")
        self.patch_autospec(config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        for _ in range(2):
            subnet = factory.make_Subnet(vlan=interface.vlan)
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.AUTO, ip="",
                subnet=subnet, interface=interface)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip=ip,
            subnet=subnet, interface=interface)
        observed = interface.release_auto_ips()
        self.assertEquals(
            1, len(observed),
            "Should have 1 AUTO IP addresses that was released.")
        self.assertEquals(subnet, observed[0].subnet)
        self.assertIsNone(observed[0].ip)

    def test__calls_remove_host_maps_if_managed_subnet(self):
        from maasserver.dns import config
        mock_remove_host_maps = self.patch_autospec(
            interface_module, "remove_host_maps")
        self.patch_autospec(interface_module, "update_host_maps")
        self.patch_autospec(config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip=ip,
            subnet=subnet, interface=interface)
        interface.release_auto_ips()
        self.assertThat(
            mock_remove_host_maps,
            MockCalledOnceWith({
                nodegroup: {ip, interface.mac_address.get_raw()},
            }))

    def test__calls_update_host_maps_for_next_ip_managed_subnet(self):
        from maasserver.dns import config
        self.patch_autospec(interface_module, "remove_host_maps")
        mock_update_host_maps = self.patch_autospec(
            interface_module, "update_host_maps")
        self.patch_autospec(config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO,
            subnet=subnet, interface=interface)
        sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=subnet, interface=interface).ip
        interface.release_auto_ips()
        self.assertThat(
            mock_update_host_maps,
            MockCalledOnceWith({
                nodegroup: {sip: interface.mac_address.get_raw()},
            }))

    def test__calls_dns_update_zones(self):
        from maasserver.dns import config
        self.patch_autospec(interface_module, "remove_host_maps")
        self.patch_autospec(interface_module, "update_host_maps")
        mock_dns_update_zones = self.patch_autospec(
            config, "dns_update_zones")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
            subnet=subnet)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.AUTO, ip=ip,
            subnet=subnet, interface=interface)
        interface.release_auto_ips()
        self.assertThat(
            mock_dns_update_zones,
            MockCalledOnceWith({nodegroup, interface.node.nodegroup}))


class TestClaimStaticIPs(MAASServerTestCase):
    """Tests for `Interface.claim_static_ips`."""

    def test__without_address_calls_link_subnet_for_each_discovered(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet_v4)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            subnet=subnet_v4, interface=interface)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=unicode(network_v6.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet_v6)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            subnet=subnet_v6, interface=interface)

        mock_link_subnet = self.patch_autospec(interface, "link_subnet")
        interface.claim_static_ips()
        self.assertThat(
            mock_link_subnet,
            MockCallsMatch(
                call(INTERFACE_LINK_TYPE.STATIC, subnet_v4),
                call(INTERFACE_LINK_TYPE.STATIC, subnet_v6)))

    def test__without_address_does_nothing_if_none_managed(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            subnet=subnet_v4, interface=interface)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=unicode(network_v6.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            subnet=subnet_v6, interface=interface)
        self.assertEquals(
            0, len(interface.claim_static_ips()),
            "No subnets should have been linked.")

    def test__with_address_raises_error_if_ip_not_in_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            subnet=subnet_v4, interface=interface)
        network_v6 = factory.make_ipv6_network()
        ip_v6 = factory.pick_ip_in_network(network_v6)
        error = self.assertRaises(
            StaticIPAddressOutOfRange, interface.claim_static_ips, ip_v6)
        self.assertEquals(
            "requested_address '%s' is not in a managed subnet for "
            "this interface '%s'" % (ip_v6, interface.name),
            error.message)

    def test__with_address_calls_link_subnet_with_ip_address(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            subnet=subnet_v4, interface=interface)
        requested_ip = factory.pick_ip_in_network(network_v4)

        mock_link_subnet = self.patch_autospec(interface, "link_subnet")
        mock_link_subnet.return_value = sentinel.claimed_ip
        [claimed_ip] = interface.claim_static_ips(requested_ip)
        self.assertThat(
            mock_link_subnet,
            MockCalledOnceWith(
                INTERFACE_LINK_TYPE.STATIC, subnet_v4,
                ip_address=requested_ip))
        self.assertEquals(sentinel.claimed_ip, claimed_ip)

    def test__device_no_address_calls_link_subnet_for_each_discovered(self):
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        parent = factory.make_Node()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet_v4)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            subnet=subnet_v4, interface=interface)
        network_v6 = factory.make_ipv6_network()
        subnet_v6 = factory.make_Subnet(cidr=unicode(network_v6.cidr))
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet_v6)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            subnet=subnet_v6, interface=interface)
        device = factory.make_Device(parent=parent)
        device_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device)

        mock_link_subnet = self.patch_autospec(device_interface, "link_subnet")
        device_interface.claim_static_ips()
        self.assertThat(
            mock_link_subnet,
            MockCallsMatch(
                call(INTERFACE_LINK_TYPE.STATIC, subnet_v4),
                call(INTERFACE_LINK_TYPE.STATIC, subnet_v6)))

    def test__device_with_address_calls_link_subnet_with_ip_address(self):
        parent = factory.make_Node()
        interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=parent)
        network_v4 = factory.make_ipv4_network()
        subnet_v4 = factory.make_Subnet(cidr=unicode(network_v4.cidr))
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip="",
            subnet=subnet_v4, interface=interface)
        device = factory.make_Device(parent=parent)
        device_interface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, node=device)
        requested_ip = factory.pick_ip_in_network(network_v4)

        mock_link_subnet = self.patch_autospec(device_interface, "link_subnet")
        mock_link_subnet.return_value = sentinel.claimed_ip
        [claimed_ip] = device_interface.claim_static_ips(requested_ip)
        self.assertThat(
            mock_link_subnet,
            MockCalledOnceWith(
                INTERFACE_LINK_TYPE.STATIC, subnet_v4,
                ip_address=requested_ip))
        self.assertEquals(sentinel.claimed_ip, claimed_ip)
