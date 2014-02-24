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
from maasserver.models import MACAddress
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
