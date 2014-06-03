# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`StaticIPAddress` tests."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from django.core.exceptions import ValidationError
from maasserver.models.staticipaddress import (
    StaticIPAddress,
    StaticIPAddressExhaustion,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from netaddr import (
    IPAddress,
    IPRange,
    )


class StaticIPAddressManagerTest(MAASServerTestCase):

    def test_allocate_new_returns_ip_in_correct_range(self):
        low, high = factory.make_ip_range()
        ipaddress = StaticIPAddress.objects.allocate_new(low, high)
        self.assertIsInstance(ipaddress, StaticIPAddress)
        iprange = IPRange(low, high)
        self.assertIn(IPAddress(ipaddress.ip), iprange)

    def test_allocate_new_raises_when_addresses_exhausted(self):
        low = high = "192.168.230.1"
        StaticIPAddress.objects.allocate_new(low, high)
        self.assertRaises(
            StaticIPAddressExhaustion,
            StaticIPAddress.objects.allocate_new, low, high)


class StaticIPAddressTest(MAASServerTestCase):

    def test_stores_to_database(self):
        ipaddress = factory.make_staticipaddress()
        self.assertEqual([ipaddress], list(StaticIPAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        ip = StaticIPAddress(ip='256.0.0.0.0')
        self.assertRaises(ValidationError, ip.full_clean)
