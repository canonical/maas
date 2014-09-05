# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `MACAddressForm`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.forms import MACAddressForm
from maasserver.models import MACAddress
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestMACAddressForm(MAASServerTestCase):

    def test_MACAddressForm_creates_mac_address(self):
        node = factory.make_Node()
        mac = factory.getRandomMACAddress()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        form.save()
        self.assertTrue(
            MACAddress.objects.filter(node=node, mac_address=mac).exists())

    def test_saves_to_db_by_default(self):
        node = factory.make_Node()
        mac = factory.getRandomMACAddress()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        form.save()
        self.assertEqual(
            mac, MACAddress.objects.get(mac_address=mac).mac_address)

    def test_does_not_save_to_db_if_commit_is_False(self):
        node = factory.make_Node()
        mac = factory.getRandomMACAddress()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        form.save(commit=False)
        self.assertItemsEqual([], MACAddress.objects.filter(mac_address=mac))

    def test_MACAddressForm_displays_error_message_if_mac_already_used(self):
        mac = factory.getRandomMACAddress()
        node = factory.make_MACAddress(address=mac)
        node = factory.make_Node()
        form = MACAddressForm(node=node, data={'mac_address': mac})
        self.assertFalse(form.is_valid())
        self.assertEquals(
            {'mac_address': ['This MAC address is already registered.']},
            form._errors)
        self.assertFalse(
            MACAddress.objects.filter(node=node, mac_address=mac).exists())
