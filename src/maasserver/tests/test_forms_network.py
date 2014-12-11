# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `NetworkForm`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver import forms as forms_module
from maasserver.dns import config as dns_config_module
from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.forms import (
    create_Network_from_NodeGroupInterface,
    NetworkForm,
    )
from maasserver.models import (
    MACAddress,
    Network,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from netaddr import IPNetwork
from testtools.matchers import Contains


class TestNetworkForm(MAASServerTestCase):
    """Tests for `NetworkForm`."""

    def test_creates_network(self):
        network = factory.make_ipv4_network()
        name = factory.make_name('network')
        definition = {
            'name': name,
            'description': factory.make_string(),
            'ip': "%s" % network.cidr.ip,
            'netmask': "%s" % network.netmask,
            'vlan_tag': factory.make_vlan_tag(),
        }
        form = NetworkForm(data=definition)
        form.save()
        network_obj = Network.objects.get(name=name)
        self.assertAttributes(network_obj, definition)

    def test_updates_network(self):
        network = factory.make_Network()
        new_description = factory.make_string()
        form = NetworkForm(
            data={'description': new_description}, instance=network)
        form.save()
        network = reload_object(network)
        self.assertEqual(new_description, network.description)

    def test_populates_initial_macaddresses(self):
        network = factory.make_Network()
        macs = [
            factory.make_MACAddress_with_Node(networks=[network])
            for _ in range(3)]
        # Create other MAC addresses.
        for _ in range(2):
            factory.make_MACAddress_with_Node(
                networks=[factory.make_Network()])
        new_description = factory.make_string()
        form = NetworkForm(
            data={'description': new_description}, instance=network)
        self.assertItemsEqual(
            [mac.mac_address.get_raw() for mac in macs],
            form.initial['mac_addresses'])

    def test_macaddresses_are_sorted(self):
        network1, network2 = factory.make_Networks(2)
        macs = [
            factory.make_MACAddress_with_Node(networks=[network1])
            for _ in range(3)]
        # Create macs connected to the same node.
        macs = macs + [
            factory.make_MACAddress(networks=[network1], node=macs[0].node)
            for _ in range(3)]
        # Create other MAC addresses.
        for _ in range(2):
            factory.make_MACAddress_with_Node(networks=[network2])
        form = NetworkForm(data={}, instance=network1)
        self.assertEqual(
            list(MACAddress.objects.all().order_by(
                'node__hostname', 'mac_address')),
            list(form.fields['mac_addresses'].queryset))

    def test_macaddresses_widget_displays_MAC_and_node_hostname(self):
        networks = factory.make_Networks(3)
        same_network = networks[0]
        misc_networks = networks[1:]
        for _ in range(3):
            factory.make_MACAddress_with_Node(networks=[same_network])
        # Create other MAC addresses.
        for network in misc_networks:
            factory.make_MACAddress_with_Node(networks=[network])
        form = NetworkForm(data={}, instance=same_network)
        self.assertItemsEqual(
            [(mac.mac_address, "%s (%s)" % (
                mac.mac_address, mac.node.hostname))
             for mac in MACAddress.objects.all()],
            form.fields['mac_addresses'].widget.choices)

    def test_updates_macaddresses(self):
        network = factory.make_Network()
        # Attach a couple of MAC addresses to the network.
        [factory.make_MACAddress_with_Node(networks=[network])
            for _ in range(3)]
        new_macs = [
            factory.make_MACAddress_with_Node()
            for _ in range(3)]
        form = NetworkForm(
            data={
                'mac_addresses': [
                    mac.mac_address.get_raw() for mac in new_macs],
            },
            instance=network)
        form.save()
        network = reload_object(network)
        self.assertItemsEqual(new_macs, network.macaddress_set.all())

    def test_deletes_macaddresses_by_default_if_not_specified(self):
        network = factory.make_Network()
        [factory.make_MACAddress_with_Node(networks=[network])
            for _ in range(3)]
        form = NetworkForm(
            data={
                'name': "foo",
            },
            instance=network)
        form.save()
        network = reload_object(network)
        self.assertItemsEqual([], network.macaddress_set.all())

    def test_does_not_delete_unspecified_macaddresses_if_told_not_to(self):
        network = factory.make_Network()
        macs = [
            factory.make_MACAddress_with_Node(networks=[network])
            for _ in range(3)]
        form = NetworkForm(
            data={
                'name': "foo",
            },
            instance=network,
            delete_macs_if_not_present=False,
            )
        form.save()
        network = reload_object(network)
        self.assertItemsEqual(macs, network.macaddress_set.all())

    def test_reports_clashes(self):
        # The uniqueness test on the Network model raises a ValidationError
        # when it finds a clash, but Django is prone to crashing when the
        # exception doesn't take the expected form (bug 1299114).
        big_network = IPNetwork('10.9.0.0/16')
        nested_network = IPNetwork('10.9.9.0/24')

        existing_network = factory.make_Network(network=big_network)
        form = NetworkForm(data={
            'name': factory.make_name('clashing-network'),
            'ip': "%s" % nested_network.cidr.ip,
            'netmask': "%s" % nested_network.netmask,
            'vlan_tag': factory.make_vlan_tag(),
            })
        self.assertFalse(form.is_valid())
        message = "IP range clashes with network '%s'." % existing_network.name
        self.assertEqual(
            {
                'ip': [message],
                'netmask': [message],
            },
            form.errors)

    def test_writes_dns_when_network_edited(self):
        write_full_dns_config = self.patch(
            dns_config_module, "write_full_dns_config")
        network = factory.make_ipv4_network()
        name = factory.make_name('network')
        definition = {
            'name': name,
            'description': factory.make_string(),
            'ip': "%s" % network.cidr.ip,
            'netmask': "%s" % network.netmask,
            'vlan_tag': factory.make_vlan_tag(),
        }
        form = NetworkForm(data=definition)
        form.save()
        self.assertThat(write_full_dns_config, MockCalledOnceWith())

    def test_writes_dns_when_network_deleted(self):
        network = factory.make_Network()
        write_full_dns_config = self.patch(
            dns_config_module, "write_full_dns_config")
        network.delete()
        self.assertThat(write_full_dns_config, MockCalledOnceWith())


class TestCreateNetworkFromNodeGroupInterface(MAASServerTestCase):

    def test_skips_creation_if_netmask_undefined(self):
        nodegroup = factory.make_NodeGroup()
        interface = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        interface.subnet_mask = None
        network = create_Network_from_NodeGroupInterface(interface)
        self.assertIsNone(network)
        self.assertItemsEqual([], Network.objects.all())

    def test_creates_network_without_vlan(self):
        nodegroup = factory.make_NodeGroup()
        interface = factory.make_NodeGroupInterface(nodegroup)
        network = create_Network_from_NodeGroupInterface(interface)
        definition = {
            'name': "%s-%s" % (
                interface.nodegroup.name, interface.interface),
            'description': (
                "Auto created when creating interface %s on cluster %s" % (
                    interface.name, interface.nodegroup.name)),
            'ip': "%s" % interface.network.ip,
            'netmask': "%s" % interface.network.netmask,
            'vlan_tag': None,
        }
        network_obj = Network.objects.get(id=network.id)
        self.assertAttributes(network_obj, definition)

    def test_creates_network_with_vlan(self):
        nodegroup = factory.make_NodeGroup()
        intf = 'eth0'
        vlan = 1
        interface = factory.make_NodeGroupInterface(
            nodegroup, interface="%s.%d" % (intf, vlan))
        network = create_Network_from_NodeGroupInterface(interface)
        net_name = "%s-%s" % (interface.nodegroup.name, interface.interface)
        net_name = net_name.replace('.', '-')
        definition = {
            'name': net_name,
            'description': (
                "Auto created when creating interface %s on cluster %s" % (
                    interface.name, interface.nodegroup.name)),
            'ip': "%s" % interface.network.ip,
            'netmask': "%s" % interface.network.netmask,
            'vlan_tag': vlan,
        }
        network_obj = Network.objects.get(id=network.id)
        self.assertAttributes(network_obj, definition)

    def test_skips_creation_if_network_already_exists(self):
        nodegroup = factory.make_NodeGroup()
        interface = factory.make_NodeGroupInterface(nodegroup)
        create_Network_from_NodeGroupInterface(interface)
        maaslog = self.patch(forms_module, 'maaslog')

        self.assertIsNone(create_Network_from_NodeGroupInterface(interface))
        self.assertEqual(
            1, maaslog.warning.call_count,
            "maaslog.warning hasn't been called")
        self.assertThat(
            maaslog.warning.call_args[0][0],
            Contains("Failed to create Network"))
