# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of subnet signals."""

from maasserver.enum import IPADDRESS_TYPE
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks


class TestSubnetSignals(MAASServerTestCase):
    scenarios = (
        ("ipv4", {"network_maker": factory.make_ipv4_network}),
        ("ipv6", {"network_maker": factory.make_ipv6_network}),
    )

    def test_creating_subnet_links_to_existing_ip_address(self):
        network = self.network_maker()
        ip = factory.pick_ip_in_network(network)
        ip_address = factory.make_StaticIPAddress(
            ip=ip, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )

        # Ensure that for this test to really be testing the logic the
        # `StaticIPAddress` needs to not have a subnet assigned.
        self.assertIsNone(ip_address.subnet)

        # Creating the subnet, must link the created `StaticIPAddress` to
        # that subnet.
        subnet = factory.make_Subnet(cidr=network.cidr)
        ip_address.refresh_from_db()
        self.assertEqual(subnet, ip_address.subnet)

    def test_updating_subnet_removes_existing_ip_address_adds_another(self):
        network1 = self.network_maker()
        network2 = self.network_maker(but_not=[network1])
        ip1 = factory.pick_ip_in_network(network1)
        ip2 = factory.pick_ip_in_network(network2)

        # Create the second IP address not linked to network2.
        ip_address2 = factory.make_StaticIPAddress(
            ip=ip2, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        self.assertIsNone(ip_address2.subnet)

        # Create the first IP address assigned to the network.
        subnet = factory.make_Subnet(cidr=network1.cidr)
        ip_address1 = factory.make_StaticIPAddress(
            ip=ip1, alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet=subnet
        )
        self.assertEqual(subnet, ip_address1.subnet)

        # Update the subnet to have the CIDR of network2.
        subnet.cidr = network2.cidr
        subnet.gateway_ip = None

        with post_commit_hooks:
            subnet.save()

        # IP1 should not have a subnet, and IP2 should not have the subnet.
        ip_address1.refresh_from_db()
        ip_address2.refresh_from_db()
        self.assertIsNone(ip_address1.subnet)
        self.assertEqual(subnet, ip_address2.subnet)
