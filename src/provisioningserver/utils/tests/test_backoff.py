# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.utils.backoff`."""


from itertools import islice

from hypothesis import given
from hypothesis.strategies import floats, lists
from testtools.matchers import (
    AllMatch,
    HasLength,
    IsInstance,
    LessThan,
    MatchesAll,
)

from maastesting.matchers import GreaterThanOrEqual
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.backoff import exponential_growth, full_jitter


class TestFunctions(MAASTestCase):
    """Test functions in `backoff`."""

    @given(floats(0.0, 10.0), floats(1.0, 3.0))
    def test_exponential_growth(self, base, rate):
        growth = exponential_growth(base, rate)
        growth_seq = list(islice(growth, 10))

        self.assertThat(growth_seq, HasLength(10))
        self.assertThat(growth_seq, AllMatch(IsInstance(float)))
        self.assertEqual(growth_seq, sorted(growth_seq))

        self.assertEqual((base * rate), growth_seq[0])
        self.assertEqual((base * (rate**10)), growth_seq[-1])

    @given(lists(floats(0.0, 10000.0), 0, 100))
    def test_full_jitter(self, values):
        jittered = list(full_jitter(values))

        self.assertThat(jittered, AllMatch(IsInstance(float)))
        self.assertThat(
            jittered,
            AllMatch(MatchesAll(GreaterThanOrEqual(0.0), LessThan(10000.0))),
        )
