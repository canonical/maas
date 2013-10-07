# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for miscellaneous helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from netaddr import IPAddress
from provisioningserver.dns.utils import generated_hostname


class TestUtilities(MAASTestCase):

    def test_generated_hostname_returns_hostname(self):
        self.assertEqual(
            '192-168-0-1', generated_hostname('192.168.0.1'))

    def test_generated_hostname_returns_hostname_plus_domain(self):
        domain = factory.getRandomString()
        self.assertEqual(
            '192-168-0-1.%s' % domain,
            generated_hostname('192.168.0.1', domain))

    def test_generated_hostname_accepts_IPAddress(self):
        address = IPAddress("12.34.56.78")
        self.assertEqual("12-34-56-78", generated_hostname(address))
