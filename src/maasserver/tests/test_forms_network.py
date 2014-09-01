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

from maasserver.dns import config as dns_config_module
from maasserver.forms import NetworkForm
from maasserver.models import (
    MACAddress,
    Network,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from netaddr import IPNetwork


class TestNetworkForm(MAASServerTestCase):
    """Tests for `NetworkForm`."""

    def test_creates_network(self):
        network = factory.getRandomNetwork()
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
        network = factory.make_network()
        new_description = factory.make_string()
        form = NetworkForm(
            data={'description': new_description}, instance=network)
        form.save()
        network = reload_object(network)
        self.assertEqual(new_description, network.description)

    def test_populates_initial_macaddresses(self):
        network = factory.make_network()
        macs = [
            factory.make_mac_address(networks=[network])
            for _ in range(3)]
        # Create other MAC addresses.
        for _ in range(2):
            factory.make_mac_address(networks=[factory.make_network()])
        new_description = factory.make_string()
        form = NetworkForm(
            data={'description': new_description}, instance=network)
        self.assertItemsEqual(
            [mac.mac_address.get_raw() for mac in macs],
            form.initial['mac_addresses'])

    def test_macaddresses_are_sorted(self):
        network1, network2 = factory.make_networks(2)
        macs = [
            factory.make_mac_address(networks=[network1])
            for _ in range(3)]
        # Create macs connected to the same node.
        macs = macs + [
            factory.make_mac_address(networks=[network1], node=macs[0].node)
            for _ in range(3)]
        # Create other MAC addresses.
        for _ in range(2):
            factory.make_mac_address(networks=[network2])
        form = NetworkForm(data={}, instance=network1)
        self.assertEqual(
            list(MACAddress.objects.all().order_by(
                'node__hostname', 'mac_address')),
            list(form.fields['mac_addresses'].queryset))

    def test_macaddresses_widget_displays_MAC_and_node_hostname(self):
        networks = factory.make_networks(3)
        same_network = networks[0]
        misc_networks = networks[1:]
        for _ in range(3):
            factory.make_mac_address(networks=[same_network])
        # Create other MAC addresses.
        for network in misc_networks:
            factory.make_mac_address(networks=[network])
        form = NetworkForm(data={}, instance=same_network)
        self.assertItemsEqual(
            [(mac.mac_address, "%s (%s)" % (
                mac.mac_address, mac.node.hostname))
             for mac in MACAddress.objects.all()],
            form.fields['mac_addresses'].widget.choices)

    def test_updates_macaddresses(self):
        network = factory.make_network()
        # Attach a couple of MAC addresses to the network.
        [factory.make_mac_address(networks=[network]) for _ in range(3)]
        new_macs = [
            factory.make_mac_address()
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

    def test_reports_clashes(self):
        # The uniqueness test on the Network model raises a ValidationError
        # when it finds a clash, but Django is prone to crashing when the
        # exception doesn't take the expected form (bug 1299114).
        big_network = IPNetwork('10.9.0.0/16')
        nested_network = IPNetwork('10.9.9.0/24')

        existing_network = factory.make_network(network=big_network)
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
        network = factory.getRandomNetwork()
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
        network = factory.make_network()
        write_full_dns_config = self.patch(
            dns_config_module, "write_full_dns_config")
        network.delete()
        self.assertThat(write_full_dns_config, MockCalledOnceWith())
