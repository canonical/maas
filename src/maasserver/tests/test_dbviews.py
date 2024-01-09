# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.dbviews`."""


from django.db import connection

from maasserver.dbviews import _ALL_VIEWS, register_all_views
from maasserver.models.subnet import Subnet
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestDatabaseViews(MAASServerTestCase):
    def test_views_contain_valid_sql(self):
        # This is a positive test case. The view creation code is very simple,
        # and will just abort with an exception if the SQL is invalid. So all
        # we just need to make sure no execeptions are thrown when the views
        # are created.
        register_all_views()

    def test_each_view_can_be_used(self):
        register_all_views()
        for view_name, view_sql in _ALL_VIEWS.items():
            with connection.cursor() as cursor:
                cursor.execute("SELECT * from %s;" % view_name)


class TestRoutablePairs(MAASServerTestCase):
    """Tests for the `maasserver_routable_pairs` view."""

    def test_contains_nothing_when_there_are_no_nodes(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * from maasserver_routable_pairs")
            self.assertEqual(len(cursor.fetchall()), 0)

    def make_node_with_address(self, cidr, space=None, vlan=None):
        node = factory.make_Node()
        iface = factory.make_Interface(node=node)
        try:
            subnet = Subnet.objects.get(cidr=cidr, vlan__space=space)
        except Subnet.DoesNotExist:
            subnet = factory.make_Subnet(cidr=cidr, space=space, vlan=vlan)
        sip = factory.make_StaticIPAddress(interface=iface, subnet=subnet)
        return node, iface, subnet, sip

    def test_contains_routes_between_nodes_on_same_subnet(self):
        network = factory.make_ip4_or_6_network()
        node1, if1, sn1, sip1 = self.make_node_with_address(network)
        node2, if2, sn2, sip2 = self.make_node_with_address(network)

        # Routes between all addresses are found, even back to themselves.
        left = node1.id, if1.id, sn1.id, sn1.vlan.id, sip1.ip
        right = node2.id, if2.id, sn2.id, sn2.vlan.id, sip2.ip

        def row(ent1, ent2, metric):
            return (*ent1, *ent2, None, metric)

        expected = [
            row(left, left, 0),
            row(left, right, 1),  # Same space, hence metric of 3.
            row(right, right, 0),
            row(right, left, 1),  # Same space, hence metric of 3.
        ]

        with connection.cursor() as cursor:
            cursor.execute("SELECT * from maasserver_routable_pairs")
            self.assertCountEqual(expected, cursor.fetchall())

    def test_contains_routes_between_nodes_on_same_vlan(self):
        vlan = factory.make_VLAN()
        network1 = factory.make_ip4_or_6_network()
        network2 = factory.make_ip4_or_6_network(version=network1.version)
        node1, if1, sn1, sip1 = self.make_node_with_address(
            network1, vlan=vlan
        )
        node2, if2, sn2, sip2 = self.make_node_with_address(
            network2, vlan=vlan
        )

        # Routes between all addresses are found, even back to themselves.
        left = node1.id, if1.id, sn1.id, sn1.vlan.id, sip1.ip
        right = node2.id, if2.id, sn2.id, sn2.vlan.id, sip2.ip

        def row(ent1, ent2, metric):
            return (*ent1, *ent2, None, metric)

        expected = [
            row(left, left, 0),
            row(left, right, 2),  # Same VLAN, hence metric of 2.
            row(right, right, 0),
            row(right, left, 2),  # Same VLAN, hence metric of 2.
        ]

        with connection.cursor() as cursor:
            cursor.execute("SELECT * from maasserver_routable_pairs")
            self.assertCountEqual(expected, cursor.fetchall())

    def test_contains_routes_between_nodes_on_same_space(self):
        space = factory.make_Space()
        network1 = factory.make_ip4_or_6_network()
        network2 = factory.make_ip4_or_6_network(version=network1.version)
        node1, if1, sn1, sip1 = self.make_node_with_address(network1, space)
        node2, if2, sn2, sip2 = self.make_node_with_address(network2, space)

        # Routes between all addresses are found, even back to themselves.
        left = node1.id, if1.id, sn1.id, sn1.vlan.id, sip1.ip
        right = node2.id, if2.id, sn2.id, sn2.vlan.id, sip2.ip

        def row(ent1, ent2, metric):
            return (*ent1, *ent2, space.id, metric)

        expected = [
            row(left, left, 0),
            row(left, right, 3),  # Same space, hence metric of 3.
            row(right, right, 0),
            row(right, left, 3),  # Same space, hence metric of 3.
        ]

        with connection.cursor() as cursor:
            cursor.execute("SELECT * from maasserver_routable_pairs")
            self.assertCountEqual(expected, cursor.fetchall())

    def test_contains_routes_between_nodes_via_null_space(self):
        network1 = factory.make_ip4_or_6_network()
        network2 = factory.make_ip4_or_6_network(version=network1.version)
        node1, if1, sn1, sip1 = self.make_node_with_address(network1)
        node2, if2, sn2, sip2 = self.make_node_with_address(network2)

        # Routes between all addresses are found, even back to themselves.
        left = node1.id, if1.id, sn1.id, sn1.vlan.id, sip1.ip
        right = node2.id, if2.id, sn2.id, sn2.vlan.id, sip2.ip

        def row(ent1, ent2, metric):
            return (*ent1, *ent2, None, metric)

        expected = [
            row(left, left, 0),
            row(left, right, 4),  # The NULL space, hence metric of 4.
            row(right, right, 0),
            row(right, left, 4),  # The NULL space, hence metric of 4.
        ]

        with connection.cursor() as cursor:
            cursor.execute("SELECT * from maasserver_routable_pairs")
            self.assertCountEqual(expected, cursor.fetchall())

    def test_does_not_contain_routes_between_nodes_on_differing_spaces(self):
        space1 = factory.make_Space()
        space2 = factory.make_Space()
        network1 = factory.make_ip4_or_6_network()
        network2 = factory.make_ip4_or_6_network(version=network1.version)
        node1, if1, sn1, sip1 = self.make_node_with_address(network1, space1)
        node2, if2, sn2, sip2 = self.make_node_with_address(network2, space2)

        # Only routes from left to left and right to right are found: right is
        # not routable from left, and left is not routable from right because
        # the spaces differ.
        left = node1.id, if1.id, sn1.id, sn1.vlan.id, sip1.ip
        right = node2.id, if2.id, sn2.id, sn2.vlan.id, sip2.ip
        expected = [
            (*left, *left, space1.id, 0),
            (*right, *right, space2.id, 0),
        ]

        with connection.cursor() as cursor:
            cursor.execute("SELECT * from maasserver_routable_pairs")
            self.assertCountEqual(expected, cursor.fetchall())

    def test_does_not_contain_routes_between_addrs_of_diff_network_fams(self):
        space = factory.make_Space()  # One space.
        network1 = factory.make_ip4_or_6_network()
        network2 = factory.make_ip4_or_6_network(
            version=(4 if network1.version == 6 else 6)
        )
        node1, if1, sn1, sip1 = self.make_node_with_address(network1, space)
        node2, if2, sn2, sip2 = self.make_node_with_address(network2, space)

        # Only routes from left to left and right to right are found: right is
        # not routable from left, and left is not routable from right because
        # the address families differ.
        left = node1.id, if1.id, sn1.id, sn1.vlan.id, sip1.ip
        right = node2.id, if2.id, sn2.id, sn2.vlan.id, sip2.ip
        expected = [(*left, *left, space.id, 0), (*right, *right, space.id, 0)]

        with connection.cursor() as cursor:
            cursor.execute("SELECT * from maasserver_routable_pairs")
            self.assertCountEqual(expected, cursor.fetchall())
