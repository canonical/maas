# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test MAC utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from maasserver.utils.mac import get_vendor_for_mac
from maastesting.testcase import MAASTestCase


class TestGetVendorForMac(MAASTestCase):

    def test_get_vendor_for_mac_returns_vendor(self):
        self.assertEqual(
            "ELITEGROUP COMPUTER SYSTEMS CO., LTD.",
            get_vendor_for_mac('ec:a8:6b:fd:ae:3f'))

    def test_get_vendor_for_mac_returns_error_message_if_unknown_mac(self):
        self.assertEqual(
            "Unknown Vendor",
            get_vendor_for_mac('aa:bb:cc:dd:ee:ff'))
