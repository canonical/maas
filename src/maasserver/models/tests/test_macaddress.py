# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`MACAddress` tests."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from operator import attrgetter

from django.core.exceptions import ValidationError
from maasserver.enum import IPADDRESS_TYPE
from maasserver.exceptions import StaticIPAddressTypeClash
from maasserver.models import (
    MACAddress,
    StaticIPAddress,
    )
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class MACAddressTest(MAASServerTestCase):

    def test_stores_to_database(self):
        mac = factory.make_mac_address()
        self.assertEqual([mac], list(MACAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        mac = MACAddress(
            mac_address='aa:bb:ccxdd:ee:ff', node=factory.make_node())
        self.assertRaises(ValidationError, mac.full_clean)

    def test_mac_not_in_any_network_by_default(self):
        mac = factory.make_mac_address()
        self.assertItemsEqual([], mac.networks.all())

    def test_mac_can_be_connected_to_multiple_networks(self):
        networks = factory.make_networks(3)
        mac = factory.make_mac_address(networks=networks)
        self.assertItemsEqual(networks, reload_object(mac).networks.all())

    def test_get_networks_returns_empty_if_no_networks(self):
        mac = factory.make_mac_address(networks=[])
        self.assertEqual([], list(mac.get_networks()))

    def test_get_networks_returns_networks(self):
        network = factory.make_network()
        mac = factory.make_mac_address(networks=[network])
        self.assertEqual([network], list(mac.get_networks()))

    def test_get_networks_sorts_by_network_name(self):
        networks = factory.make_networks(3, sortable_name=True)
        mac = factory.make_mac_address(networks=networks)
        self.assertEqual(
            sorted(networks, key=attrgetter('name')),
            list(mac.get_networks()))

    def test_unicode_copes_with_unclean_unicode_mac_address(self):
        # If MACAddress.mac_address has not been cleaned yet, it will
        # contain a string rather than a MAC.  Make sure __unicode__
        # handles this.
        mac_str = "aa:bb:cc:dd:ee:ff"
        mac = MACAddress(
            mac_address=mac_str, node=factory.make_node())
        self.assertEqual(mac_str, unicode(mac))

    def test_unicode_copes_with_unclean_bytes_mac_address(self):
        # If MACAddress.mac_address has not been cleaned yet, it will
        # contain a string rather than a MAC.  Make sure __str__
        # handles this.
        bytes_mac = bytes("aa:bb:cc:dd:ee:ff")
        mac = MACAddress(
            mac_address=bytes_mac, node=factory.make_node())
        self.assertEqual(bytes_mac, mac.__str__())


class TestMACAddressForStaticIPClaiming(MAASServerTestCase):

    def test_claim_static_ip_returns_none_if_no_cluster_interface(self):
        # If mac.cluster_interface is None, we can't allocate any IP.
        mac = factory.make_mac_address()
        self.assertIsNone(mac.claim_static_ip())

    def test_claim_static_ip_reserves_an_ip_address(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        mac = node.get_primary_mac()
        claimed_ip = mac.claim_static_ip()
        self.assertIsInstance(claimed_ip, StaticIPAddress)
        self.assertNotEqual([], list(node.static_ip_addresses()))
        self.assertEqual(
            IPADDRESS_TYPE.AUTO, StaticIPAddress.objects.all()[0].alloc_type)

    def test_claim_static_ip_sets_type_as_required(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        mac = node.get_primary_mac()
        claimed_ip = mac.claim_static_ip(alloc_type=IPADDRESS_TYPE.STICKY)
        self.assertEqual(IPADDRESS_TYPE.STICKY, claimed_ip.alloc_type)

    def test_claim_static_ip_returns_none_if_no_static_range_defined(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        mac = node.get_primary_mac()
        mac.cluster_interface.static_ip_range_low = None
        mac.cluster_interface.static_ip_range_high = None
        self.assertIsNone(mac.claim_static_ip())

    def test_claim_static_ip_raises_if_clashing_type(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        mac = node.get_primary_mac()
        iptype = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
        iptype2 = factory.pick_enum(IPADDRESS_TYPE, but_not=[iptype])
        mac.claim_static_ip(alloc_type=iptype)
        self.assertRaises(
            StaticIPAddressTypeClash,
            mac.claim_static_ip, alloc_type=iptype2)

    def test_claim_static_ip_returns_existing_if_claiming_same_type(self):
        node = factory.make_node_with_mac_attached_to_nodegroupinterface()
        mac = node.get_primary_mac()
        iptype = factory.pick_enum(
            IPADDRESS_TYPE, but_not=[IPADDRESS_TYPE.USER_RESERVED])
        ip = mac.claim_static_ip(alloc_type=iptype)
        self.assertEqual(
            ip, mac.claim_static_ip(alloc_type=iptype))
