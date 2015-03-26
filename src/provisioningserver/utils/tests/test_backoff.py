# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.utils.backoff`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from itertools import islice

from hypothesis import (
    assume,
    given,
)
from hypothesis.specifiers import floats_in_range
from maastesting.matchers import GreaterThanOrEqual
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.backoff import (
    exponential_growth,
    full_jitter,
)
from testtools.matchers import (
    AllMatch,
    HasLength,
    IsInstance,
    LessThan,
    MatchesAll,
)


class TestFunctions(MAASTestCase):
    """Test functions in `backoff`."""

    @given(floats_in_range(0.0, 10.0), floats_in_range(1.0, 3.0))
    def test_exponential_growth(self, base, rate):
        # Hypothesis generates rates that are less than 1.0 in contradiction
        # to the given specifier. This appears to be a bug, but we can work
        # around it with assume().
        assume(rate >= 1.0)

        growth = exponential_growth(base, rate)
        growth_seq = list(islice(growth, 10))

        self.assertThat(growth_seq, HasLength(10))
        self.assertThat(growth_seq, AllMatch(IsInstance(float)))
        self.assertEqual(growth_seq, sorted(growth_seq))

        self.assertEqual((base * rate), growth_seq[0])
        self.assertEqual((base * (rate ** 10)), growth_seq[-1])

    @given([floats_in_range(0.0, 10000.0)])
    def test_full_jitter(self, values):
        jittered = list(full_jitter(values))

        self.assertThat(jittered, AllMatch(IsInstance(float)))
        self.assertThat(jittered, AllMatch(MatchesAll(
            GreaterThanOrEqual(0.0), LessThan(10000.0))))
