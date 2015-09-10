# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `0145_populate_subnets` migration.

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

from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.models import (
    Fabric,
    NodeGroupInterface,
    Space,
    Subnet,
    VLAN,
)
from maasserver.models.migrations import populate_subnets_helper as helper
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import IPNetwork
from testtools.matchers import Equals


@unittest.skip("Can no longer test this migration; fields have been deleted.")
class TestPopulateSubnetsMigration(MAASServerTestCase):

    def do_forward_migration(self):
        self.migrate_networks_forward()
        self.migrate_nodegroupinterfaces_forward()

    def migrate_nodegroupinterfaces_forward(self):
        now = datetime.now()
        default_vlan = VLAN.objects.get_default_vlan()
        default_space = Space.objects.get_default_space()

        helper._migrate_nodegroupinterfaces_forward(
            now, NodeGroupInterface, Subnet, default_space, default_vlan)

    def migrate_networks_forward(self):
        now = datetime.now()
        default_fabric = Fabric.objects.get_default_fabric()
        default_vlan = VLAN.objects.get_default_vlan()
        default_space = Space.objects.get_default_space()

        helper._migrate_networks_forward(
            now, Network, Subnet, VLAN, default_fabric,
            default_space, default_vlan)

    def migrate_subnets_backwards(self):
        now = datetime.now()
        helper._migrate_subnets_backwards(
            now, NodeGroupInterface, Network, Subnet)

    def do_reverse_migration(self):
        self.migrate_subnets_backwards()

    @unittest.skip("Can no longer test this migration; missing fields")
    def test__nodegroupinterface_migrated(self):
        nodegroup = factory.make_NodeGroup()
        ngi = factory.make_NodeGroupInterface(nodegroup)

        self.do_forward_migration()
        subnet = Subnet.objects.first()
        self.assertThat(subnet.gateway_ip, Equals(ngi.router_ip))
        self.assertThat(subnet.cidr, Equals(
            helper._get_cidr_for_nodegroupinterface(ngi)))

    @unittest.skip("Can no longer test this migration; missing fields")
    def test__nodegroupinterface_with_no_network_in_default_vlan(self):
        nodegroup = factory.make_NodeGroup()
        factory.make_NodeGroupInterface(nodegroup)

        self.do_forward_migration()
        subnet = Subnet.objects.first()
        self.assertThat(subnet.vlan, Equals(VLAN.objects.get_default_vlan()))

    @unittest.skip("Can no longer test this migration; missing fields")
    def test__migrated_nodegroupinterface_subnet_has_default_space(self):
        nodegroup = factory.make_NodeGroup()
        factory.make_NodeGroupInterface(nodegroup)

        self.do_forward_migration()
        subnet = Subnet.objects.first()
        self.assertThat(subnet.space, Equals(
            Space.objects.get_default_space()))

    @unittest.skip("Can no longer test this migration; missing fields")
    def test__migrated_network_subnet_has_default_space(self):
        factory.make_Network()

        self.do_forward_migration()
        subnet = Subnet.objects.first()
        self.assertThat(subnet.space, Equals(
            Space.objects.get_default_space()))

    @unittest.skip("Can no longer test this migration; missing fields")
    def test__migrated_nodegroupinterface_subnet_linked(self):
        nodegroup = factory.make_NodeGroup()
        ngi = factory.make_NodeGroupInterface(nodegroup)

        self.do_forward_migration()
        subnet = Subnet.objects.first()
        ngi = reload_object(ngi)
        self.assertThat(ngi.subnet, Equals(subnet))

    @unittest.skip("Can no longer test this migration; missing fields")
    def test__nodegroupinterface_with_network_and_vlan_subnet_has_vlan(self):
        nodegroup = factory.make_NodeGroup()
        ngi = factory.make_NodeGroupInterface(nodegroup)
        network = factory.make_Network(
            network=ngi.network, default_gateway=ngi.router_ip,
            vlan_tag=factory.make_vlan_tag(allow_none=False))

        self.do_forward_migration()
        subnet = Subnet.objects.first()
        self.assertThat(subnet.vlan, Equals(VLAN.objects.get(
            vid=network.vlan_tag)))

    @unittest.skip("Can no longer test this migration; missing fields")
    def test__nodegroupinterfaces_with_identical_subnets_migrated(self):
        nodegroup = factory.make_NodeGroup()
        # MAAS only allows overlapping subnets if one of the
        # NodeGroupInterfaces is unmanaged. So make sure one is managed,
        # and the other isn't.
        ngi = factory.make_NodeGroupInterface(
            nodegroup,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
        )
        ngi2 = factory.make_NodeGroupInterface(
            nodegroup,
            network=ngi.network,
            router_ip=ngi.router_ip,
            broadcast_ip=ngi.broadcast_ip,
            subnet_mask=ngi.subnet_mask,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED,
        )

        self.do_forward_migration()

        self.assertThat(Subnet.objects.count(), Equals(1))
        subnet = Subnet.objects.first()
        self.assertThat(subnet.gateway_ip, Equals(ngi.router_ip))
        self.assertThat(subnet.gateway_ip, Equals(ngi2.router_ip))
        self.assertThat(subnet.cidr, Equals(
            helper._get_cidr_for_nodegroupinterface(ngi)))
        self.assertThat(subnet.cidr, Equals(
            helper._get_cidr_for_nodegroupinterface(ngi2)))

    @unittest.skip("Can no longer test this migration; missing fields")
    def test__nodegroupinterface_with_corresponding_network_migrated(self):
        nodegroup = factory.make_NodeGroup()
        ngi = factory.make_NodeGroupInterface(nodegroup)
        network = factory.make_Network(
            network=ngi.network, default_gateway=ngi.router_ip)

        self.do_forward_migration()

        self.assertThat(Subnet.objects.count(), Equals(1))
        subnet = Subnet.objects.first()
        self.assertThat(subnet.gateway_ip, Equals(ngi.router_ip))
        self.assertThat(subnet.cidr, Equals(
            helper._get_cidr_for_nodegroupinterface(ngi)))
        self.assertThat(subnet.cidr, Equals(
            helper._get_cidr_for_network(network)))
        self.assertThat(subnet.vlan.vid, Equals(network.vlan_tag))

    @unittest.skip("Can no longer test this migration; missing fields")
    def test__migrate_networks_forward(self):
        network = factory.make_Network()
        self.migrate_networks_forward()
        subnet = Subnet.objects.first()
        self.assertThat(network.ip, Equals(
            unicode(IPNetwork(subnet.cidr).network)))
        self.assertThat(network.netmask, Equals(
            unicode(IPNetwork(subnet.cidr).netmask)))
        if network.dns_servers is not None and network.dns_servers != '':
            self.assertThat(network.dns_servers, Equals(
                ' '.join(subnet.dns_servers)))
        else:
            self.assertThat(subnet.dns_servers, Equals([]))
        if (network.default_gateway is not None
                and network.default_gateway != ''):
            self.assertThat(network.default_gateway, Equals(subnet.gateway_ip))
        else:
            self.assertIsNone(subnet.gateway_ip)
        self.assertThat(network.vlan_tag, Equals(subnet.vlan.vid))
