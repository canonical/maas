# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for interface link form."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.forms_interface_link import (
    InterfaceLinkForm,
    InterfaceUnlinkForm,
)
from maasserver.models import interface as interface_module
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one
from netaddr import IPAddress


class TestInterfaceLinkForm(MAASServerTestCase):

    def test__requires_mode(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(instance=interface, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "mode": ["This field is required."],
            }, form.errors)

    def test__mode_is_case_insensitive(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.DHCP.lower(),
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test__sets_subnet_queryset_to_subnets_on_interface_vlan(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnets = [
            factory.make_Subnet(vlan=interface.vlan)
            for _ in range(3)
        ]
        form = InterfaceLinkForm(instance=interface, data={})
        self.assertItemsEqual(subnets, form.fields["subnet"].queryset)

    def test__DHCP_not_allowed_if_already_DHCP_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        dhcp_subnet = factory.make_Subnet()
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="",
            subnet=dhcp_subnet, interface=interface)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.DHCP,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "mode": [
                "Interface is already set to DHCP from '%s'." % (
                    dhcp_subnet)]
            }, form.errors)

    def test__DHCP_not_allowed_if_already_DHCP_without_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        static_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="", interface=interface)
        static_ip.subnet = None
        static_ip.save()
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.DHCP,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "mode": [
                "Interface is already set to DHCP."]
            }, form.errors)

    def test__DHCP_creates_link_to_DHCP_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        dhcp_subnet = factory.make_Subnet(vlan=interface.vlan)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.DHCP,
            "subnet": dhcp_subnet.id,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        dhcp_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.DHCP)
        self.assertEquals(dhcp_subnet, dhcp_ip.subnet)

    def test__DHCP_creates_link_to_DHCP_without_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.DHCP,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.DHCP)))

    def test__STATIC_requires_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.STATIC,
        })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "subnet": ["This field is required."],
            }, form.errors)

    def test__STATIC_not_allowed_if_ip_address_not_in_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(
            vlan=interface.vlan, cidr=unicode(network.cidr))
        ip_not_in_subnet = factory.make_ipv6_address()
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.STATIC,
            "subnet": subnet.id,
            "ip_address": ip_not_in_subnet,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "ip_address": [
                "IP address is not in the given subnet '%s'." % subnet]
            }, form.errors)

    def test__STATIC_not_allowed_if_ip_address_in_dynamic_range(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        ip_in_dynamic = IPAddress(ngi.get_dynamic_ip_range().first)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.STATIC,
            "subnet": subnet.id,
            "ip_address": "%s" % ip_in_dynamic,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "ip_address": [
                "IP address is inside a managed dynamic range %s to %s." % (
                    ngi.ip_range_low, ngi.ip_range_high)]
            }, form.errors)

    def test__STATIC_sets_ip_in_unmanaged_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.STATIC,
            "subnet": subnet.id,
            "ip_address": ip,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(
                    alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet)))

    def test__STATIC_sets_ip_in_managed_subnet(self):
        # Silence update_host_maps.
        self.patch_autospec(interface_module, "update_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        ip_in_static = IPAddress(ngi.get_static_ip_range().first)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.STATIC,
            "subnet": subnet.id,
            "ip_address": "%s" % ip_in_static,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        self.assertIsNotNone(
            get_one(
                interface.ip_addresses.filter(
                    alloc_type=IPADDRESS_TYPE.STICKY, ip="%s" % ip_in_static,
                    subnet=subnet)))

    def test__STATIC_picks_ip_in_unmanaged_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.STATIC,
            "subnet": subnet.id,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        ip_address = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet))
        self.assertIsNotNone(ip_address)
        self.assertIn(IPAddress(ip_address.ip), subnet.get_ipnetwork())

    def test__STATIC_picks_ip_in_managed_subnet(self):
        # Silence update_host_maps.
        self.patch_autospec(interface_module, "update_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        ngi = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=subnet)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.STATIC,
            "subnet": subnet.id,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        ip_address = get_one(
            interface.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, subnet=subnet))
        self.assertIsNotNone(ip_address)
        self.assertIn(IPAddress(ip_address.ip), ngi.get_static_ip_range())

    def test__LINK_UP_not_allowed_with_other_ip_addresses(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP, ip="", interface=interface)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.LINK_UP,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "mode": [
                "Cannot configure interface to link up (with no IP address)"
                "while other links are already configured."]
            }, form.errors)

    def test__LINK_UP_creates_link_STICKY_with_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        link_subnet = factory.make_Subnet(vlan=interface.vlan)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.LINK_UP,
            "subnet": link_subnet.id,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        link_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.STICKY)
        self.assertIsNone(link_ip.ip)
        self.assertEquals(link_subnet, link_ip.subnet)

    def test__LINK_UP_creates_link_STICKY_without_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceLinkForm(instance=interface, data={
            "mode": INTERFACE_LINK_TYPE.LINK_UP,
            })
        self.assertTrue(form.is_valid(), form.errors)
        interface = form.save()
        link_ip = get_one(
            interface.ip_addresses.filter(alloc_type=IPADDRESS_TYPE.STICKY))
        self.assertIsNotNone(link_ip)
        self.assertIsNone(link_ip.ip)


class TestInterfaceUnlinkForm(MAASServerTestCase):

    def test__requires_id(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        form = InterfaceUnlinkForm(instance=interface, data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "id": ["This field is required."],
            }, form.errors)

    def test__must_be_valid_id(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        link_id = random.randint(100, 1000)
        form = InterfaceUnlinkForm(instance=interface, data={
            "id": link_id,
            })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "id": ["'%s' is not a valid id.  It should be one of: ." % (
                link_id)],
            }, form.errors)

    def test__DHCP_deletes_link_with_unmanaged_subnet(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        dhcp_subnet = factory.make_Subnet(vlan=interface.vlan)
        interface.link_subnet(INTERFACE_LINK_TYPE.DHCP, dhcp_subnet)
        interface = reload_object(interface)
        dhcp_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.DHCP)
        form = InterfaceUnlinkForm(instance=interface, data={
            "id": dhcp_ip.id,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertIsNone(reload_object(dhcp_ip))

    def test__DHCP_deletes_link_with_managed_subnet(self):
        self.patch_autospec(interface_module, "remove_host_maps")
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        dhcp_subnet = factory.make_Subnet(vlan=interface.vlan)
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            subnet=dhcp_subnet)
        interface.link_subnet(INTERFACE_LINK_TYPE.DHCP, dhcp_subnet)
        interface = reload_object(interface)
        dhcp_ip = interface.ip_addresses.get(alloc_type=IPADDRESS_TYPE.DHCP)
        assigned_ip = factory.pick_ip_in_network(dhcp_subnet.get_ipnetwork())
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=assigned_ip,
            subnet=dhcp_subnet, interface=interface)
        form = InterfaceUnlinkForm(instance=interface, data={
            "id": dhcp_ip.id,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertIsNone(reload_object(dhcp_ip))

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
        form = InterfaceUnlinkForm(instance=interface, data={
            "id": static_ip.id,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertIsNone(reload_object(static_ip))

    def test__STATIC_deletes_link_in_managed_subnet(self):
        self.patch_autospec(interface_module, "remove_host_maps")
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
        form = InterfaceUnlinkForm(instance=interface, data={
            "id": static_ip.id,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertIsNone(reload_object(static_ip))

    def test__LINK_UP_deletes_link(self):
        interface = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        subnet = factory.make_Subnet(vlan=interface.vlan)
        link_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip="",
            subnet=subnet, interface=interface)
        form = InterfaceUnlinkForm(instance=interface, data={
            "id": link_ip.id,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertIsNone(reload_object(link_ip))
