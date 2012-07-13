# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the :class:`DHCPLease` model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.models.dhcplease import DHCPLease
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.utils import ignore_unused


def get_leases(nodegroup):
    """Return DHCPLease records for `nodegroup`."""
    return DHCPLease.objects.filter(nodegroup=nodegroup)


def map_leases(nodegroup):
    """Return IP/MAC mappings dict for leases in `nodegroup`."""
    return {lease.ip: lease.mac for lease in get_leases(nodegroup)}


class TestDHCPLease(TestCase):
    """Tests for :class:`DHCPLease`."""

    def test_init(self):
        nodegroup = factory.make_node_group()
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()

        lease = DHCPLease(nodegroup=nodegroup, ip=ip, mac=mac)
        lease.save()

        self.assertItemsEqual([lease], get_leases(nodegroup))
        self.assertEqual(nodegroup, lease.nodegroup)
        self.assertEqual(ip, lease.ip)
        self.assertEqual(mac, lease.mac)


class TestDHCPLeaseManager(TestCase):
    """Tests for :class:`DHCPLeaseManager`."""

    def test_update_leases_accepts_empty_leases(self):
        nodegroup = factory.make_node_group()
        DHCPLease.objects.update_leases(nodegroup, {})
        self.assertItemsEqual([], get_leases(nodegroup))

    def test_update_leases_creates_new_lease(self):
        nodegroup = factory.make_node_group()
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        DHCPLease.objects.update_leases(nodegroup, {ip: mac})
        self.assertEqual({ip: mac}, map_leases(nodegroup))

    def test_update_leases_deletes_obsolete_lease(self):
        nodegroup = factory.make_node_group()
        factory.make_dhcp_lease(nodegroup=nodegroup)
        DHCPLease.objects.update_leases(nodegroup, {})
        self.assertItemsEqual([], get_leases(nodegroup))

    def test_update_leases_replaces_reassigned_ip(self):
        nodegroup = factory.make_node_group()
        ip = factory.getRandomIPAddress()
        factory.make_dhcp_lease(nodegroup=nodegroup, ip=ip)
        new_mac = factory.getRandomMACAddress()
        DHCPLease.objects.update_leases(nodegroup, {ip: new_mac})
        self.assertEqual({ip: new_mac}, map_leases(nodegroup))

    def test_update_leases_keeps_unchanged_mappings(self):
        original_lease = factory.make_dhcp_lease()
        nodegroup = original_lease.nodegroup
        DHCPLease.objects.update_leases(
            nodegroup, {original_lease.ip: original_lease.mac})
        self.assertItemsEqual([original_lease], get_leases(nodegroup))

    def test_update_leases_adds_new_ip_to_mac(self):
        nodegroup = factory.make_node_group()
        mac = factory.getRandomMACAddress()
        ip1 = factory.getRandomIPAddress()
        ip2 = factory.getRandomIPAddress()
        factory.make_dhcp_lease(nodegroup=nodegroup, mac=mac, ip=ip1)
        DHCPLease.objects.update_leases(nodegroup, {ip1: mac, ip2: mac})
        self.assertEqual({ip1: mac, ip2: mac}, map_leases(nodegroup))

    def test_update_leases_deletes_only_obsolete_ips(self):
        nodegroup = factory.make_node_group()
        mac = factory.getRandomMACAddress()
        obsolete_ip = factory.getRandomIPAddress()
        current_ip = factory.getRandomIPAddress()
        factory.make_dhcp_lease(nodegroup=nodegroup, mac=mac, ip=obsolete_ip)
        factory.make_dhcp_lease(nodegroup=nodegroup, mac=mac, ip=current_ip)
        DHCPLease.objects.update_leases(nodegroup, {current_ip: mac})
        self.assertEqual({current_ip: mac}, map_leases(nodegroup))

    def test_update_leases_leaves_other_nodegroups_alone(self):
        innocent_nodegroup = factory.make_node_group()
        innocent_lease = factory.make_dhcp_lease(nodegroup=innocent_nodegroup)
        DHCPLease.objects.update_leases(
            factory.make_node_group(),
            {factory.getRandomIPAddress(): factory.getRandomMACAddress()})
        self.assertItemsEqual(
            [innocent_lease], get_leases(innocent_nodegroup))

    def test_update_leases_combines_additions_deletions_and_replacements(self):
        nodegroup = factory.make_node_group()
        mac1 = factory.getRandomMACAddress()
        mac2 = factory.getRandomMACAddress()
        obsolete_lease = factory.make_dhcp_lease(
            nodegroup=nodegroup, mac=mac1)
        # The obsolete lease won't be in the update, so it'll disappear.
        ignore_unused(obsolete_lease)
        unchanged_lease = factory.make_dhcp_lease(
            nodegroup=nodegroup, mac=mac1)
        reassigned_lease = factory.make_dhcp_lease(
            nodegroup=nodegroup, mac=mac1)
        new_ip = factory.getRandomIPAddress()
        DHCPLease.objects.update_leases(nodegroup, {
            reassigned_lease.ip: mac2,
            unchanged_lease.ip: mac1,
            new_ip: mac1,
        })
        self.assertEqual(
            {
                reassigned_lease.ip: mac2,
                unchanged_lease.ip: mac1,
                new_ip: mac1,
            },
            map_leases(nodegroup))

    def test_get_hostname_ip_mapping_returns_mapping(self):
        nodegroup = factory.make_node_group()
        expected_mapping = {}
        for i in range(3):
            node = factory.make_node(
                nodegroup=nodegroup, set_hostname=True)
            mac = factory.make_mac_address(node=node)
            factory.make_mac_address(node=node)
            lease = factory.make_dhcp_lease(
                nodegroup=nodegroup, mac=mac.mac_address)
            expected_mapping[node.hostname] = lease.ip
        mapping = DHCPLease.objects.get_hostname_ip_mapping(nodegroup)
        self.assertEqual(expected_mapping, mapping)

    def test_get_hostname_ip_mapping_considers_only_first_mac(self):
        nodegroup = factory.make_node_group()
        node = factory.make_node(
            nodegroup=nodegroup, set_hostname=True)
        factory.make_mac_address(node=node)
        second_mac = factory.make_mac_address(node=node)
        # Create a lease for the second MAC Address.
        factory.make_dhcp_lease(
            nodegroup=nodegroup, mac=second_mac.mac_address)
        mapping = DHCPLease.objects.get_hostname_ip_mapping(nodegroup)
        self.assertEqual({}, mapping)

    def test_get_hostname_ip_mapping_considers_given_nodegroup(self):
        nodegroup = factory.make_node_group()
        node = factory.make_node(
            nodegroup=nodegroup, set_hostname=True)
        mac = factory.make_mac_address(node=node)
        factory.make_dhcp_lease(
            nodegroup=nodegroup, mac=mac.mac_address)
        another_nodegroup = factory.make_node_group()
        mapping = DHCPLease.objects.get_hostname_ip_mapping(
            another_nodegroup)
        self.assertEqual({}, mapping)
