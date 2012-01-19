# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test MACAddressField."""

from __future__ import print_function

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from maas.testing import TestCase
from maasserver.macaddress import validate_mac
from maasserver.models import MACAddress
from maasserver.testing.factory import factory


class TestMACAddressField(TestCase):

    def test_mac_address_is_stored_normalized_and_loaded(self):
        stored_mac = factory.make_mac_address('AA-bb-CC-dd-EE-Ff')
        stored_mac.save()
        loaded_mac = MACAddress.objects.get(id=stored_mac.id)
        self.assertEqual('aa:bb:cc:dd:ee:ff', loaded_mac.mac_address)

    def test_accepts_colon_separated_octets(self):
        validate_mac('00:aa:22:cc:44:dd')
        # No error.
        pass

    def test_accepts_dash_separated_octets(self):
        validate_mac('00-aa-22-cc-44-dd')
        # No error.
        pass

    def test_accepts_upper_and_lower_case(self):
        validate_mac('AA:BB:CC:dd:ee:ff')
        # No error.
        pass

    def test_rejects_short_mac(self):
        self.assertRaises(ValidationError, validate_mac, '00:11:22:33:44')

    def test_rejects_long_mac(self):
        self.assertRaises(
            ValidationError, validate_mac, '00:11:22:33:44:55:66')

    def test_rejects_short_octet(self):
        self.assertRaises(ValidationError, validate_mac, '00:1:22:33:44:55')

    def test_rejects_long_octet(self):
        self.assertRaises(ValidationError, validate_mac, '00:11:222:33:44:55')
