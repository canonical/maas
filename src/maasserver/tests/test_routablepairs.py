# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.routablepairs`."""

__all__ = []

from itertools import product

from maasserver.dbviews import register_view
from maasserver.models.node import Node
from maasserver.routablepairs import find_addresses_between_nodes
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools import ExpectedException


class TestFindAddressesBetweenNodes(MAASServerTestCase):
    """Tests for `maasserver.routablepairs.find_addresses_between_nodes`."""

    def setUp(self):
        super(TestFindAddressesBetweenNodes, self).setUp()
        register_view("maasserver_routable_pairs")

    def test__yields_nothing_when_no_nodes_given(self):
        self.assertItemsEqual(
            [], find_addresses_between_nodes([], []))

    def test__rejects_unsaved_nodes_on_the_left(self):
        saved_node, unsaved_node = factory.make_Node(), Node()
        with ExpectedException(AssertionError, ".* not in the database"):
            list(find_addresses_between_nodes([unsaved_node], [saved_node]))

    def test__rejects_unsaved_nodes_on_the_right(self):
        saved_node, unsaved_node = factory.make_Node(), Node()
        with ExpectedException(AssertionError, ".* not in the database"):
            list(find_addresses_between_nodes([saved_node], [unsaved_node]))

    def make_node_with_address(self, space, cidr):
        node = factory.make_Node()
        iface = factory.make_Interface(node=node)
        subnet = factory.make_Subnet(space=space, cidr=cidr)
        sip = factory.make_StaticIPAddress(interface=iface, subnet=subnet)
        return node, sip.get_ipaddress()

    def test__yields_routes_between_nodes_on_same_space(self):
        space = factory.make_Space()
        network1 = factory.make_ip4_or_6_network()
        network2 = factory.make_ip4_or_6_network(version=network1.version)
        node1, ip1 = self.make_node_with_address(space, network1)
        node2, ip2 = self.make_node_with_address(space, network2)

        left = node1, ip1
        right = node2, ip2
        expected = [left + right]

        # A route from node1 to node2 is found.
        self.assertItemsEqual(
            expected, find_addresses_between_nodes([node1], [node2]))

    def test__yields_routes_between_multiple_nodes_on_same_space(self):
        space = factory.make_Space()

        lefts, rights = [], []
        for index in range(3):
            network1 = factory.make_ip4_or_6_network()
            network2 = factory.make_ip4_or_6_network(version=network1.version)
            lefts.append(self.make_node_with_address(space, network1))
            rights.append(self.make_node_with_address(space, network2))

        expected = [
            (n1, ip1, n2, ip2)
            for (n1, ip1), (n2, ip2) in product(lefts, rights)
            # Addresses are only routable when they're the same IP version.
            if ip1.version == ip2.version
        ]

        # A route from each node on the left is found to each on the right.
        self.assertItemsEqual(
            expected, find_addresses_between_nodes(
                (node for node, _ in lefts), (node for node, _ in rights)))

    def test__does_not_contain_routes_between_nodes_on_differing_spaces(self):
        space1 = factory.make_Space()
        space2 = factory.make_Space()
        network1 = factory.make_ip4_or_6_network()
        network2 = factory.make_ip4_or_6_network(version=network1.version)
        node1, ip1 = self.make_node_with_address(space1, network1)
        node2, ip2 = self.make_node_with_address(space2, network2)

        expected = []

        # No routable addresses are found.
        self.assertItemsEqual(
            expected, find_addresses_between_nodes([node1], [node2]))

    def test__does_not_contain_routes_between_addrs_of_diff_network_fams(self):
        space = factory.make_Space()  # One space.
        network1 = factory.make_ip4_or_6_network()
        network2 = factory.make_ip4_or_6_network(
            version=(4 if network1.version == 6 else 6))
        node1, ip1 = self.make_node_with_address(space, network1)
        node2, ip2 = self.make_node_with_address(space, network2)

        expected = []

        # No routable addresses are found.
        self.assertItemsEqual(
            expected, find_addresses_between_nodes([node1], [node2]))
