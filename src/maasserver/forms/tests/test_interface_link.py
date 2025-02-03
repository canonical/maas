# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for interface link form."""


import random

from netaddr import IPAddress

from maasserver.enum import INTERFACE_LINK_TYPE, INTERFACE_TYPE, IPADDRESS_TYPE
from maasserver.forms.interface_link import (
    InterfaceLinkForm,
    InterfaceSetDefaultGatwayForm,
    InterfaceUnlinkForm,
)
from maasserver.models import Subnet
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one, post_commit_hooks, reload_object


class TestInterfaceLinkForm(MAASServerTestCase):
    def test_requires_mode(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(instance=interface, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"mode": ["This field is required."]}, form.errors)

    def test_mode_is_case_insensitive(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(
            instance=interface, data={"mode": INTERFACE_LINK_TYPE.DHCP.upper()}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_sets_subnet_queryset_to_all_on_interface_wihtout_vlan(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        interface.vlan = None
        interface.save()
        form = InterfaceLinkForm(instance=interface, data={})
        self.assertCountEqual(
            list(Subnet.objects.all()), list(form.fields["subnet"].queryset)
        )

    def test_sets_subnet_queryset_to_subnets_on_interface_vlan(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnets = [factory.make_Subnet(vlan=interface.vlan) for _ in range(3)]
        form = InterfaceLinkForm(instance=interface, data={})
        self.assertCountEqual(subnets, form.fields["subnet"].queryset)

    def test_AUTO_requires_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(
            instance=interface, data={"mode": INTERFACE_LINK_TYPE.AUTO}
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"subnet": ["This field is required."]}, form.errors)

    def test_AUTO_creates_link_to_AUTO_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        auto_subnet = factory.make_Subnet(vlan=interface.vlan)
        form = InterfaceLinkForm(
            instance=interface,
            data={"mode": INTERFACE_LINK_TYPE.AUTO, "subnet": auto_subnet.id},
        )
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        auto_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.AUTO)
        self.assertEqual(auto_subnet, auto_ip.subnet)

    def test_AUTO_sets_node_gateway_link_v4(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network = factory.make_ipv4_network()
        auto_subnet = factory.make_Subnet(
            cidr=str(network.cidr), vlan=interface.vlan
        )
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.AUTO,
                "subnet": auto_subnet.id,
                "default_gateway": True,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        auto_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.AUTO)
        node = interface.get_node()
        self.assertEqual(auto_ip, node.gateway_link_ipv4)

    def test_AUTO_sets_node_gateway_link_v6(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network = factory.make_ipv6_network()
        auto_subnet = factory.make_Subnet(
            cidr=str(network.cidr), vlan=interface.vlan
        )
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.AUTO,
                "subnet": auto_subnet.id,
                "default_gateway": True,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        auto_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.AUTO)
        node = interface.get_node()
        self.assertEqual(auto_ip, node.gateway_link_ipv6)

    def test_AUTO_default_gateway_requires_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(
            instance=interface,
            data={"mode": INTERFACE_LINK_TYPE.AUTO, "default_gateway": True},
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "default_gateway": [
                    "Subnet is required when default_gateway is True."
                ],
                "subnet": ["This field is required."],
            },
            form.errors,
        )

    def test_AUTO_default_gateway_requires_subnet_with_gateway_ip(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        auto_subnet = factory.make_Subnet(vlan=interface.vlan)
        auto_subnet.gateway_ip = None
        auto_subnet.save()
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.AUTO,
                "subnet": auto_subnet.id,
                "default_gateway": True,
            },
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "default_gateway": [
                    "Cannot set as default gateway because subnet "
                    "%s doesn't provide a gateway IP address." % auto_subnet
                ]
            },
            form.errors,
        )

    def test_DHCP_not_allowed_if_already_DHCP_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        dhcp_subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP,
            ip="",
            subnet=dhcp_subnet,
            interface=interface,
        )
        form = InterfaceLinkForm(
            instance=interface, data={"mode": INTERFACE_LINK_TYPE.DHCP}
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "mode": [
                    "Interface is already set to DHCP from '%s'." % dhcp_subnet
                ]
            },
            form.errors,
        )

    def test_DHCP_not_allowed_if_already_DHCP_without_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="", interface=interface
        )
        static_ip.subnet = None
        static_ip.save()
        form = InterfaceLinkForm(
            instance=interface, data={"mode": INTERFACE_LINK_TYPE.DHCP}
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {"mode": ["Interface is already set to DHCP."]}, form.errors
        )

    def test_DHCP_not_allowed_default_gateway(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(
            instance=interface,
            data={"mode": INTERFACE_LINK_TYPE.DHCP, "default_gateway": True},
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "default_gateway": [
                    "Cannot use in mode '%s'." % (INTERFACE_LINK_TYPE.DHCP)
                ]
            },
            form.errors,
        )

    def test_DHCP_creates_link_to_DHCP_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        dhcp_subnet = factory.make_Subnet(vlan=interface.vlan)
        form = InterfaceLinkForm(
            instance=interface,
            data={"mode": INTERFACE_LINK_TYPE.DHCP, "subnet": dhcp_subnet.id},
        )
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        dhcp_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.DHCP)
        self.assertEqual(dhcp_subnet, dhcp_ip.subnet)

    def test_DHCP_creates_link_to_DHCP_without_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(
            instance=interface, data={"mode": INTERFACE_LINK_TYPE.DHCP}
        )
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DHCP)
            )
        )

    def test_STATIC_requires_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(
            instance=interface, data={"mode": INTERFACE_LINK_TYPE.STATIC}
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"subnet": ["This field is required."]}, form.errors)

    def test_STATIC_not_allowed_if_ip_address_not_in_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=str(network.cidr)
        )
        ip_not_in_subnet = factory.make_ipv6_address()
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": subnet.id,
                "ip_address": ip_not_in_subnet,
            },
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "ip_address": [
                    "IP address is not in the given subnet '%s'." % subnet
                ]
            },
            form.errors,
        )

    def test_STATIC_not_allowed_if_ip_address_in_dynamic_range(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_ipv4_Subnet_with_IPRanges(vlan=interface.vlan)
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip_in_dynamic = factory.pick_ip_in_IPRange(dynamic_range)
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": subnet.id,
                "ip_address": "%s" % ip_in_dynamic,
            },
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "ip_address": [
                    "IP address is inside a dynamic range %s to %s."
                    % (dynamic_range.start_ip, dynamic_range.end_ip)
                ]
            },
            form.errors,
        )

    def test_STATIC_sets_ip_in_unmanaged_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": subnet.id,
                "ip_address": ip,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            interface = form.save()
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(
                    alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
                )
            )
        )

    def test_STATIC_sets_ip_for_unmanaged_subnet_specifier(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": "%s" % subnet.name,
                "ip_address": ip,
            },
        )
        self.assertTrue(form.is_valid(), dict(form.errors))

        with post_commit_hooks:
            interface = form.save()
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(
                    alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
                )
            )
        )

    def test_STATIC_sets_ip_for_subnet_cidr_specifier(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": "cidr:%s" % subnet.cidr,
                "ip_address": ip,
            },
        )
        self.assertTrue(form.is_valid(), dict(form.errors))

        with post_commit_hooks:
            interface = form.save()
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(
                    alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
                )
            )
        )

    def test_STATIC_sets_ip_in_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ip_in_subnet = factory.pick_ip_in_Subnet(subnet)
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": subnet.id,
                "ip_address": "%s" % ip_in_subnet,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            interface = form.save()
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(
                    alloc_type=IPADDRESS_TYPE.STICKY,
                    ip="%s" % ip_in_subnet,
                    subnet=subnet,
                )
            )
        )

    def test_STATIC_picks_ip_in_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        form = InterfaceLinkForm(
            instance=interface,
            data={"mode": INTERFACE_LINK_TYPE.STATIC, "subnet": subnet.id},
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            interface = form.save()

        ip_address = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet
            )
        )
        self.assertIsNotNone(ip_address)
        self.assertIn(IPAddress(ip_address.ip), subnet.get_ipnetwork())

    def test_STATIC_sets_node_gateway_link_ipv4(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(
            cidr=str(network.cidr), vlan=interface.vlan
        )
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": subnet.id,
                "default_gateway": True,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            interface = form.save()

        ip_address = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet
            )
        )
        node = interface.get_node()
        self.assertEqual(ip_address, node.gateway_link_ipv4)

    def test_STATIC_sets_node_gateway_link_ipv6(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network = factory.make_ipv6_network()
        subnet = factory.make_Subnet(
            cidr=str(network.cidr), vlan=interface.vlan
        )
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": subnet.id,
                "default_gateway": True,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            interface = form.save()

        ip_address = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet
            )
        )
        node = interface.get_node()
        self.assertEqual(ip_address, node.gateway_link_ipv6)

    def test_STATIC_set_link_with_numa_on_rack_controller(self):
        rack_controller = factory.make_RackController()
        numa = factory.make_NUMANode(node=rack_controller)
        iface = factory.make_Interface(node=rack_controller, numa_node=numa)
        network = factory.make_ipv6_network()
        subnet = factory.make_Subnet(cidr=str(network.cidr), vlan=iface.vlan)
        form = InterfaceLinkForm(
            instance=iface,
            data={
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": subnet.id,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_LINK_UP_not_allowed_with_other_ip_addresses(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="", interface=interface
        )
        form = InterfaceLinkForm(
            instance=interface, data={"mode": INTERFACE_LINK_TYPE.LINK_UP}
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "mode": [
                    "Cannot configure interface to link up (with no IP address) "
                    "while other links are already configured. Specify force=True "
                    "to override this behavior and delete all links."
                ]
            },
            form.errors,
        )

    def test_LINK_UP_creates_link_STICKY_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        link_subnet = factory.make_Subnet(vlan=interface.vlan)
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "subnet": link_subnet.id,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            interface = form.save()

        link_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.STICKY)
        self.assertIsNone(link_ip.ip)
        self.assertEqual(link_subnet, link_ip.subnet)

    def test_LINK_UP_creates_link_STICKY_without_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(
            instance=interface, data={"mode": INTERFACE_LINK_TYPE.LINK_UP}
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            interface = form.save()

        link_ip = get_one(
            interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.STICKY)
        )
        self.assertIsNotNone(link_ip)
        self.assertIsNone(link_ip.ip)

    def test_LINK_UP_not_allowed_default_gateway(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(
            instance=interface,
            data={
                "mode": INTERFACE_LINK_TYPE.LINK_UP,
                "default_gateway": True,
            },
        )
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "default_gateway": [
                    "Cannot use in mode '%s'." % (INTERFACE_LINK_TYPE.LINK_UP)
                ]
            },
            form.errors,
        )

    def test_linking_when_no_bond_not_allowed(self):
        node = factory.make_Node()
        eth0 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        eth1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND, parents=[eth0, eth1], node=node
        )
        subnet = factory.make_Subnet(vlan=eth0.vlan)
        ip_in_static = factory.pick_ip_in_Subnet(subnet)
        form = InterfaceLinkForm(
            instance=eth0,
            data={
                "mode": INTERFACE_LINK_TYPE.STATIC,
                "subnet": subnet.id,
                "ip_address": "%s" % ip_in_static,
            },
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "bond": [
                    (
                        "Cannot link interface(%s) when interface is in a "
                        "bond(%s)." % (eth0.name, bond0.name)
                    )
                ]
            },
            form.errors,
        )


class TestInterfaceUnlinkForm(MAASServerTestCase):
    def test_requires_id(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceUnlinkForm(instance=interface, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"id": ["This field is required."]}, form.errors)

    def test_must_be_valid_id(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        link_id = random.randint(100, 1000)
        form = InterfaceUnlinkForm(instance=interface, data={"id": link_id})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "id": [
                    "'%s' is not a valid id.  It should be one of: ." % link_id
                ]
            },
            form.errors,
        )

    def test_DHCP_deletes_link_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        dhcp_subnet = factory.make_Subnet(vlan=interface.vlan)

        with post_commit_hooks:
            interface.link_subnet(INTERFACE_LINK_TYPE.DHCP, dhcp_subnet)

        interface = reload_object(interface)
        dhcp_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.DHCP)
        form = InterfaceUnlinkForm(instance=interface, data={"id": dhcp_ip.id})
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            form.save()

        self.assertIsNone(reload_object(dhcp_ip))

    def test_STATIC_deletes_link_in_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())

        with post_commit_hooks:
            interface.link_subnet(
                INTERFACE_LINK_TYPE.STATIC, subnet, ip_address=ip
            )

        interface = reload_object(interface)
        static_ip = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
            )
        )
        form = InterfaceUnlinkForm(
            instance=interface, data={"id": static_ip.id}
        )
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            form.save()

        self.assertIsNone(reload_object(static_ip))

    def test_LINK_UP_deletes_link(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)

        with post_commit_hooks:
            link_ip = factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.STICKY,
                ip="",
                subnet=subnet,
                interface=interface,
            )
        form = InterfaceUnlinkForm(instance=interface, data={"id": link_ip.id})
        self.assertTrue(form.is_valid(), form.errors)

        with post_commit_hooks:
            form.save()

        self.assertIsNone(reload_object(link_ip))


class TestInterfaceSetDefaultGatwayForm(MAASServerTestCase):
    def make_ip_family_link(
        self, interface, network, alloc_type=IPADDRESS_TYPE.STICKY
    ):
        subnet = factory.make_Subnet(
            cidr=str(network.cidr), vlan=interface.vlan
        )
        if alloc_type == IPADDRESS_TYPE.STICKY:
            ip = factory.pick_ip_in_network(network)
        else:
            ip = ""
        return factory.make_StaticIPAddress(
            alloc_type=alloc_type, ip=ip, subnet=subnet, interface=interface
        )

    def test_interface_needs_gateways(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceSetDefaultGatwayForm(instance=interface, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {"__all__": ["This interface has no usable gateways."]},
            form.errors,
        )

    def test_doesnt_require_link_id_if_only_one_gateway_per_family(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        self.make_ip_family_link(interface, factory.make_ipv4_network())
        self.make_ip_family_link(interface, factory.make_ipv6_network())
        form = InterfaceSetDefaultGatwayForm(instance=interface, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_requires_link_id_if_more_than_one_gateway_per_family(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        self.make_ip_family_link(interface, factory.make_ipv4_network())
        self.make_ip_family_link(interface, factory.make_ipv6_network())
        self.make_ip_family_link(interface, factory.make_ipv4_network())
        self.make_ip_family_link(interface, factory.make_ipv6_network())
        form = InterfaceSetDefaultGatwayForm(instance=interface, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {
                "link_id": [
                    "This field is required; Interface has more than one "
                    "usable IPv4 and IPv6 gateways."
                ]
            },
            form.errors,
        )

    def test_link_id_fields_setup_correctly(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        links = []
        for _ in range(2):
            links.append(
                self.make_ip_family_link(
                    interface, factory.make_ipv4_network()
                )
            )
        for _ in range(2):
            links.append(
                self.make_ip_family_link(
                    interface, factory.make_ipv6_network()
                )
            )
        link_ids = [link.id for link in links]
        form = InterfaceSetDefaultGatwayForm(instance=interface, data={})
        choice_ids = [choice[0] for choice in form.fields["link_id"].choices]
        self.assertCountEqual(link_ids, choice_ids)

    def test_sets_gateway_links_works_on_dhcp_with_gateway_ip(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        ipv4_link = self.make_ip_family_link(
            interface, factory.make_ipv4_network(), IPADDRESS_TYPE.DHCP
        )
        ipv6_link = self.make_ip_family_link(
            interface, factory.make_ipv6_network(), IPADDRESS_TYPE.DHCP
        )
        form = InterfaceSetDefaultGatwayForm(instance=interface, data={})
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        node = interface.get_node()
        self.assertEqual(ipv4_link, node.gateway_link_ipv4)
        self.assertEqual(ipv6_link, node.gateway_link_ipv6)

    def test_sets_gateway_links_on_node_when_no_link_id(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        ipv4_link = self.make_ip_family_link(
            interface, factory.make_ipv4_network()
        )
        ipv6_link = self.make_ip_family_link(
            interface, factory.make_ipv6_network()
        )
        form = InterfaceSetDefaultGatwayForm(instance=interface, data={})
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        node = interface.get_node()
        self.assertEqual(ipv4_link, node.gateway_link_ipv4)
        self.assertEqual(ipv6_link, node.gateway_link_ipv6)

    def test_sets_gateway_link_v4_on_node_when_link_id(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        ipv4_link = self.make_ip_family_link(
            interface, factory.make_ipv4_network()
        )
        self.make_ip_family_link(interface, factory.make_ipv4_network())
        form = InterfaceSetDefaultGatwayForm(
            instance=interface, data={"link_id": ipv4_link.id}
        )
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        node = interface.get_node()
        self.assertEqual(ipv4_link, node.gateway_link_ipv4)

    def test_sets_gateway_link_v6_on_node_when_link_id(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        ipv6_link = self.make_ip_family_link(
            interface, factory.make_ipv6_network()
        )
        self.make_ip_family_link(interface, factory.make_ipv6_network())
        form = InterfaceSetDefaultGatwayForm(
            instance=interface, data={"link_id": ipv6_link.id}
        )
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        node = interface.get_node()
        self.assertEqual(ipv6_link, node.gateway_link_ipv6)
