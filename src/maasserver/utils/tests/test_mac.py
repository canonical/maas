# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test MAC utilities."""


from unittest.mock import MagicMock

from maasserver.testing.factory import factory
from maasserver.utils import mac
from maasserver.utils.mac import get_vendor_for_mac, is_mac
from maastesting.matchers import IsNonEmptyString
from maastesting.testcase import MAASTestCase


class TestGetVendorForMac(MAASTestCase):
    def test_get_vendor_for_mac_returns_vendor(self):
        mac_address = "ec:a8:6b:fd:ae:3f"
        self.assertThat(get_vendor_for_mac(mac_address), IsNonEmptyString)

    def test_get_vendor_for_mac_returns_error_message_if_unknown_mac(self):
        self.assertEqual(
            "Unknown Vendor", get_vendor_for_mac("aa:bb:cc:dd:ee:ff")
        )

    def test_get_vendor_for_mac_handlers_unicode_error(self):
        try:
            b"\xD3".decode("ascii")
        except UnicodeDecodeError as exc:
            error = exc
        eui_result = MagicMock()
        eui_result.oui.registration.side_effect = error
        self.patch(mac, "EUI").return_value = eui_result
        self.assertEqual(
            "Unknown Vendor", get_vendor_for_mac(factory.make_mac_address())
        )

    def test_get_vendor_survives_index_error(self):
        try:
            arr = []
            arr[3]
        except IndexError as exc:
            error = exc
        eui_result = MagicMock()
        eui_result.oui.registration.side_effect = error
        self.patch(mac, "EUI").return_value = eui_result
        self.assertEqual(
            "Unknown Vendor", get_vendor_for_mac(factory.make_mac_address())
        )


class TestIsMac(MAASTestCase):
    def test_true(self):
        self.assertTrue(is_mac(factory.make_MAC()))

    def test_false(self):
        self.assertFalse(is_mac(factory.make_name("bad")))
