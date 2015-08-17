# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `0161_create_missing_physical_interfaces` migration.

WARNING: These tests will become obsolete very quickly, as they are testing
migrations against fields that may be removed. When these tests become
obsolete, they should be skipped. The tests should be kept until at least
the next release cycle (through MAAS 1.9) in case any bugs with this migration
occur.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from datetime import datetime
import unittest

from maasserver.enum import INTERFACE_TYPE
from maasserver.models import (
    Interface,
    MACAddress,
    StaticIPAddress,
    Subnet,
    VLAN,
)
from maasserver.models.interface import INTERFACE_TYPE_MAPPING
from maasserver.models.migrations import (
    create_physical_interfaces_helper as helper,
)
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import IPAddress
from testtools.matchers import (
    AllMatch,
    Contains,
    Equals,
    HasLength,
)


class TestFindMacsHavingNoInterfaces(MAASServerTestCase):

    def test__returns_macs(self):
        orphaned = [
            factory.make_MACAddress(iftype=None)
            for _ in range(3)
        ]
        for iftype in INTERFACE_TYPE_MAPPING.keys():
            mac = factory.make_MACAddress()
            factory.make_Interface(iftype, mac=mac)
        self.assertItemsEqual(
            orphaned, helper.find_macs_having_no_interfaces(MACAddress))


class TestCreatePhysicalInterfaces(MAASServerTestCase):

    scenarios = (
        ("WithCluster", dict(with_cluster=True)),
        ("WithoutCluster", dict(with_cluster=False)),
    )

    def make_mac(self):
        mac = factory.make_MACAddress(iftype=None)
        if self.with_cluster:
            ng = factory.make_NodeGroup()
            ngi = factory.make_NodeGroupInterface(
                nodegroup=ng, network=factory._make_random_network())
            mac.cluster_interface = ngi
            mac.save()
        return mac

    def make_mac_with_static_ip(self):
        for _ in range(3):
            mac = self.make_mac()
            net = factory._make_random_network()
            if mac.cluster_interface:
                factory.make_StaticIPAddress(
                    mac=mac, ip=unicode(IPAddress(
                        mac.cluster_interface.subnet.get_cidr().first)))
                self.assertIsNotNone(mac.cluster_interface.subnet)
            else:
                factory.make_StaticIPAddress(
                    mac=mac, ip=unicode(IPAddress(net.first)))
                factory.make_Subnet(cidr=net)

    def test_creates_physical_interface(self):
        self.make_mac()
        self.assertThat(Interface.objects.all(), HasLength(0))
        helper.create_physical_interfaces(MACAddress, Interface, Subnet, VLAN)
        self.assertThat(Interface.objects.all(), HasLength(1))

    def test_ignores_macs_with_existing_interfaces(self):
        mac = self.make_mac()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, mac=mac)
        self.assertThat(Interface.objects.all(), HasLength(1))
        helper.create_physical_interfaces(MACAddress, Interface, Subnet, VLAN)
        self.assertThat(Interface.objects.all(), HasLength(1))

    def test_associates_subnets_for_each_ip(self):
        self.make_mac_with_static_ip()
        self.assertThat(Subnet.objects.all(), HasLength(3))
        helper.create_physical_interfaces(MACAddress, Interface, Subnet, VLAN)
        # Not using AllMatch() here, because we're checking that each
        # individual object is internally consistent.
        for ip in StaticIPAddress.objects.all():
            self.expectThat(ip.subnet.get_cidr(), Contains(IPAddress(ip.ip)))

    def test_creates_human_readable_interface_names(self):
        node = factory.make_Node()
        for _ in range(3):
            mac = self.make_mac()
            mac.node = node
            mac.save()
        helper.create_physical_interfaces(MACAddress, Interface, Subnet, VLAN)
        self.assertItemsEqual(
            ['eth0', 'eth1', 'eth2'],
            [interface.name for interface in Interface.objects.all()])

    def test_creates_human_readable_interface_names_on_per_node_basis(self):
        for _ in range(3):
            node = factory.make_Node()
            mac = self.make_mac()
            mac.node = node
            mac.save()
        helper.create_physical_interfaces(MACAddress, Interface, Subnet, VLAN)
        self.assertThat(
            [interface.name for interface in Interface.objects.all()],
            AllMatch(Equals('eth0')))
