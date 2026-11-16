# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for network/cluster interface helpers."""

from random import randint

from maasserver.utils.interfaces import (
    get_name_and_vlan_from_cluster_interface,
    make_name_from_interface,
)
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestMakeNameFromInterface(MAASTestCase):
    """Tests for `make_name_from_interface`."""

    def test_passes_name_unchanged(self):
        name = factory.make_name("itf9:2")
        self.assertEqual(name, make_name_from_interface(name))

    def test_escapes_weird_characters(self):
        self.assertEqual("x--y", make_name_from_interface("x?y"))
        self.assertEqual("x--y", make_name_from_interface("x y"))

    def test_makes_up_name_if_no_interface_given(self):
        self.assertNotIn(make_name_from_interface(None), (None, ""))
        self.assertNotIn(make_name_from_interface(""), (None, ""))

    def test_makes_up_unique_name_if_no_interface_given(self):
        self.assertNotEqual(
            make_name_from_interface(""), make_name_from_interface("")
        )


class TestGetNameAndVlanFromClusterInterface(MAASTestCase):
    """Tests for `get_name_and_vlan_from_cluster_interface`."""

    def make_interface(self):
        """Return a simple network interface name."""
        return "eth%d" % randint(0, 99)

    def test_returns_simple_name_unaltered(self):
        cluster = factory.make_name("cluster")
        interface = factory.make_name("iface")
        expected_name = f"{cluster}-{interface}"
        self.assertEqual(
            (expected_name, None),
            get_name_and_vlan_from_cluster_interface(cluster, interface),
        )

    def test_substitutes_colon(self):
        cluster = factory.make_name("cluster")
        base_interface = self.make_interface()
        alias = randint(0, 99)
        interface = "%s:%d" % (base_interface, alias)
        expected_name = "%s-%s-%d" % (cluster, base_interface, alias)
        self.assertEqual(
            (expected_name, None),
            get_name_and_vlan_from_cluster_interface(cluster, interface),
        )

    def test_returns_with_vlan_tag(self):
        cluster = factory.make_name("cluster")
        base_interface = self.make_interface()
        vlan_tag = factory.make_vlan_tag()
        interface = "%s.%d" % (base_interface, vlan_tag)
        expected_name = "%s-%s-%d" % (cluster, base_interface, vlan_tag)
        self.assertEqual(
            (expected_name, "%d" % vlan_tag),
            get_name_and_vlan_from_cluster_interface(cluster, interface),
        )

    def test_returns_name_with_alias_and_vlan_tag(self):
        cluster = factory.make_name("cluster")
        base_interface = self.make_interface()
        vlan_tag = factory.make_vlan_tag()
        alias = randint(0, 99)
        interface = "%s:%d.%d" % (base_interface, alias, vlan_tag)
        expected_name = "%s-%s-%d-%d" % (
            cluster,
            base_interface,
            alias,
            vlan_tag,
        )
        self.assertEqual(
            (expected_name, "%d" % vlan_tag),
            get_name_and_vlan_from_cluster_interface(cluster, interface),
        )

    def test_returns_name_with_vlan_tag_and_alias(self):
        cluster = factory.make_name("cluster")
        base_interface = self.make_interface()
        vlan_tag = factory.make_vlan_tag()
        alias = randint(0, 99)
        interface = "%s.%d:%d" % (base_interface, vlan_tag, alias)
        expected_name = "%s-%s-%d-%d" % (
            cluster,
            base_interface,
            vlan_tag,
            alias,
        )
        self.assertEqual(
            (expected_name, "%d" % vlan_tag),
            get_name_and_vlan_from_cluster_interface(cluster, interface),
        )
