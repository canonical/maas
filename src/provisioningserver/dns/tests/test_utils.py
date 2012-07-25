# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for miscellaneous helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver.dns.utils import generated_hostname


class TestUtilities(TestCase):

    def test_generated_hostname_returns_hostname(self):
        self.assertEqual(
            '192-168-0-1', generated_hostname('192.168.0.1'))

    def test_generated_hostname_returns_hostname_plus_domain(self):
        domain = factory.getRandomString()
        self.assertEqual(
            '192-168-0-1.%s' % domain,
            generated_hostname('192.168.0.1', domain))
