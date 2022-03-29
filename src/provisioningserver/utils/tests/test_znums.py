# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.utils.znums`."""


from hypothesis import given
from hypothesis.strategies import integers
from testtools.matchers import Equals

from maastesting.testcase import MAASTestCase
from provisioningserver.utils.znums import from_int, to_int


class TestZNumbers(MAASTestCase):
    def test_from_int_basics(self):
        self.assertThat(from_int(-1), Equals("3"))
        self.assertThat(from_int(0), Equals("3"))
        self.assertThat(from_int(1), Equals("4"))
        self.assertThat(from_int(24**5), Equals("433333"))
        self.assertThat(from_int(24**5 - 1), Equals("yyyyy"))

    def test_to_int_basics(self):
        self.assertThat(to_int(""), Equals(0))
        self.assertThat(to_int("3"), Equals(0))
        self.assertThat(to_int("4"), Equals(1))
        self.assertThat(to_int("433333"), Equals(24**5))
        self.assertThat(to_int("yyyyy"), Equals(24**5 - 1))

    @given(integers(0, 2**64))
    def test_roundtrip(self, num):
        self.assertThat(to_int(from_int(num)), Equals(num))

    # This range is relevant because every znum within it should be 6 digits
    # long, giving a range of ~183 million distinct znums. We expect znums of
    # the same number of digits to sort lexicographically in the same order as
    # their magnitude.
    six_digit_range = integers((24**5), (24**6) - 1)

    @given(six_digit_range, six_digit_range)
    def test_sorting_6_digit_znums(self, a, b):
        za, zb = from_int(a), from_int(b)
        self.assertThat(len(za), Equals(6))
        self.assertThat(len(zb), Equals(6))
        if a == b:
            self.assertTrue(za == zb)
        elif a < b:
            self.assertTrue(za < zb)
        elif a > b:
            self.assertTrue(za > zb)
        else:
            self.fail("Universe broken")
