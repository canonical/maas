# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test DNS module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.dns import (
    next_zone_serial,
    zone_serial,
    )
from maasserver.testing.testcase import TestCase
from testtools.matchers import MatchesStructure


class TestDNSUtilities(TestCase):

    def test_zone_serial_parameters(self):
        self.assertThat(
            zone_serial,
            MatchesStructure.byEquality(
                maxvalue=2 ** 32 - 1,
                minvalue=1,
                incr=1,
                )
            )

    def test_next_zone_serial_returns_sequence(self):
        self.assertSequenceEqual(
            ['%0.10d' % i for i in range(1, 11)],
            [next_zone_serial() for i in range(10)])
