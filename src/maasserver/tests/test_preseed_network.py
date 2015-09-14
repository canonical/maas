# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `maasserver.preseed_network`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []

from textwrap import dedent

from maasserver.dns.zonegenerator import get_dns_server_address
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
)
from maasserver.preseed_network import compose_curtin_network_config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    ContainsDict,
    Equals,
    IsInstance,
    MatchesDict,
    MatchesListwise,
)
import yaml


class AssertNetworkConfigMixin:

    IFACE_CONFIG = dedent("""\
        - id: %(name)s
          name: %(name)s
          type: physical
          mac_address: %(mac)s
        """)

    BOND_CONFIG = dedent("""\
        - id: %(name)s
          name: %(name)s
          type: bond
          mac_address: %(mac)s
          bond_interfaces:
        """)

    BRIDGE_CONFIG = dedent("""\
        - id: %(name)s
          name: %(name)s
          type: bridge
          mac_address: %(mac)s
          bridge_interfaces:
        """)

    VLAN_CONFIG = dedent("""\
        - id: %(name)s
          name: %(name)s
          type: vlan
          vlan_link: %(parent)s
          vlan_id: %(vlan_id)s
        """)

    def assertNetworkConfig(self, expected, output):
        output = output[0]
        output = yaml.load(output)
        self.assertThat(output, ContainsDict({
            "network_commands": MatchesDict({
                "builtin": Equals(["curtin", "net-meta", "custom"]),
            }),
            "network": MatchesDict({
                "version": Equals(1),
                "config": IsInstance(list),
            }),
        }))
        expected_network = yaml.load(expected)
        output_network = output["network"]["config"]
        expected_equals = map(Equals, expected_network)
        self.assertThat(output_network, MatchesListwise(expected_equals))

    def collect_interface_config(self, node, filter="physical"):
        interfaces = node.interface_set.filter(enabled=True).order_by('id')
        if filter:
            interfaces = interfaces.filter(type=filter)

        gateways = node.get_default_gateways()
        ipv4_gateway_set, ipv6_gateway_set = False, False

        def set_gateway_ip(iface, subnet, ret, ipv4_set, ipv6_set):
            ip_family = subnet.get_ipnetwork().version
            if ip_family == IPADDRESS_FAMILY.IPv4 and ipv4_set:
                return (ret, ipv4_set, ipv6_set)
            elif ip_family == IPADDRESS_FAMILY.IPv6 and ipv6_set:
                return (ret, ipv4_set, ipv6_set)
            for gateway in gateways:
                if gateway is not None:
                    iface_id, subnet_id, gateway_ip = gateway
                    if (iface_id == iface.id and
                            subnet_id == subnet.id and
                            gateway_ip == subnet.gateway_ip):
                        ret += "    gateway: %s\n" % gateway_ip
                        if ip_family == IPADDRESS_FAMILY.IPv4:
                            ipv4_set = True
                        elif ip_family == IPADDRESS_FAMILY.IPv6:
                            ipv6_set = True
            return (ret, ipv4_set, ipv6_set)

        ret = ""
        for iface in interfaces:
            self.assertIn(iface.type, ["physical", "bond", "vlan"])
            fmt_dict = {"name": iface.name, "mac": unicode(iface.mac_address)}
            if iface.type == "physical":
                ret += self.IFACE_CONFIG % fmt_dict
            elif iface.type == "bridge":
                ret += self.BRIDGE_CONFIG % fmt_dict
                for parent in iface.parents.order_by('id'):
                    ret += "  - %s" % parent.name
            elif iface.type == "bond":
                ret += self.BOND_CONFIG % fmt_dict
                for parent in iface.parents.order_by('id'):
                    ret += "  - %s\n" % parent.name
            elif iface.type == "vlan":
                fmt_dict['parent'] = iface.parents.first().get_name()
                fmt_dict['vlan_id'] = iface.vlan.vid
                ret += self.VLAN_CONFIG % fmt_dict
            addresses = iface.ip_addresses.exclude(
                alloc_type__in=[
                    IPADDRESS_TYPE.DISCOVERED,
                    IPADDRESS_TYPE.DHCP,
                ]).order_by('id')
            if len(addresses):
                ret += "  subnets:\n"
                for address in addresses:
                    subnet = address.subnet
                    if subnet is not None:
                        subnet_len = subnet.cidr.split('/')[1]
                        ret += "  - address: %s/%s\n" % (
                            unicode(address.ip), subnet_len)
                        ret += "    type: static\n"
                        ret, ipv4_gateway_set, ipv6_gateway_set = (
                            set_gateway_ip(
                                iface, subnet, ret,
                                ipv4_gateway_set, ipv6_gateway_set))
                        if subnet.dns_servers is not None:
                            ret += "    dns_nameservers:\n"
                            for dns_server in subnet.dns_servers:
                                ret += "    - %s\n" % dns_server
                dhcp_types = set()
                for dhcp_ip in iface.ip_addresses.filter(
                        alloc_type=IPADDRESS_TYPE.DHCP):
                    if dhcp_ip.subnet is None:
                        dhcp_types.add(4)
                        dhcp_types.add(6)
                    else:
                        dhcp_types.add(
                            dhcp_ip.subnet.get_ipnetwork().version)
                if dhcp_types == set([4, 6]):
                    ret += "  - type: dhcp\n"
                elif dhcp_types == set([4]):
                    ret += "  - type: dhcp4\n"
                elif dhcp_types == set([6]):
                    ret += "  - type: dhcp6\n"
        return ret

    def collectDNSConfig(self, node):
        return "- type: nameserver\n  address: %s" % (
            get_dns_server_address(nodegroup=node.nodegroup))


class TestSimpleNetworkLayout(MAASServerTestCase, AssertNetworkConfigMixin):

    def test__renders_expected_output(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            interface_count=2)
        for iface in node.interface_set.filter(enabled=True):
            factory.make_StaticIPAddress(
                interface=iface,
                subnet=iface.vlan.subnet_set.first())
        extra_interface = node.interface_set.all()[1]
        sip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=None, interface=extra_interface)
        sip.subnet = None
        sip.save()
        factory.make_Interface(node=node)
        net_config = self.collect_interface_config(node)
        net_config += self.collectDNSConfig(node)
        config = compose_curtin_network_config(node)
        self.assertNetworkConfig(net_config, config)


class TestBondNetworkLayout(MAASServerTestCase, AssertNetworkConfigMixin):

    def test__renders_expected_output(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            interface_count=2)
        interfaces = node.interface_set.all()
        vlan = node.interface_set.first().vlan
        bond_iface = factory.make_Interface(
            iftype=INTERFACE_TYPE.BOND, node=node, vlan=vlan,
            parents=interfaces)
        factory.make_StaticIPAddress(
            interface=bond_iface, alloc_type=IPADDRESS_TYPE.STICKY,
            subnet=bond_iface.vlan.subnet_set.first())
        net_config = self.collect_interface_config(node, filter="physical")
        net_config += self.collect_interface_config(node, filter="bond")
        net_config += self.collectDNSConfig(node)
        config = compose_curtin_network_config(node)
        self.assertNetworkConfig(net_config, config)


class TestVLANNetworkLayout(MAASServerTestCase, AssertNetworkConfigMixin):

    def test__renders_expected_output(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            interface_count=1)
        interfaces = node.interface_set.all()
        vlan_iface = factory.make_Interface(
            iftype=INTERFACE_TYPE.VLAN, node=node, parents=interfaces)
        subnet = factory.make_Subnet(vlan=vlan_iface.vlan)
        factory.make_StaticIPAddress(interface=vlan_iface, subnet=subnet)
        net_config = self.collect_interface_config(node, filter="physical")
        net_config += self.collect_interface_config(node, filter="vlan")
        net_config += self.collectDNSConfig(node)
        config = compose_curtin_network_config(node)
        self.assertNetworkConfig(net_config, config)


class TestVLANOnBondNetworkLayout(MAASServerTestCase,
                                  AssertNetworkConfigMixin):

    def test__renders_expected_output(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            interface_count=2)
        phys_ifaces = node.interface_set.all()
        phys_vlan = node.interface_set.first().vlan
        bond_iface = factory.make_Interface(iftype=INTERFACE_TYPE.BOND,
                                            node=node, vlan=phys_vlan,
                                            parents=phys_ifaces)
        vlan_iface = factory.make_Interface(
            iftype=INTERFACE_TYPE.VLAN, node=node, parents=[bond_iface])
        subnet = factory.make_Subnet(vlan=vlan_iface.vlan)
        factory.make_StaticIPAddress(interface=vlan_iface, subnet=subnet)
        net_config = self.collect_interface_config(node, filter="physical")
        net_config += self.collect_interface_config(node, filter="bond")
        net_config += self.collect_interface_config(node, filter="vlan")
        net_config += self.collectDNSConfig(node)
        config = compose_curtin_network_config(node)
        self.assertNetworkConfig(net_config, config)
