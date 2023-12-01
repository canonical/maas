# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from itertools import islice

from hypothesis import given
from hypothesis.strategies import floats, lists

from maastesting.testcase import MAASTestCase
from provisioningserver.utils.backoff import exponential_growth, full_jitter


class TestFunctions(MAASTestCase):
    """Test functions in `backoff`."""

    @given(floats(0.0, 10.0), floats(1.0, 3.0))
    def test_exponential_growth(self, base, rate):
        growth = exponential_growth(base, rate)
        growth_seq = list(islice(growth, 10))

        self.assertEqual(len(growth_seq), 10)
        for thing in growth_seq:
            self.assertIsInstance(thing, float)
        self.assertEqual(growth_seq, sorted(growth_seq))

        self.assertEqual((base * rate), growth_seq[0])
        self.assertEqual((base * (rate**10)), growth_seq[-1])

    @given(lists(floats(0.0, 10000.0), min_size=0, max_size=100))
    def test_full_jitter(self, values):
        jittered = list(full_jitter(values))

        for thing in jittered:
            self.assertIsInstance(thing, float)
            self.assertGreaterEqual(thing, 0.0)
            self.assertLess(thing, 10000.0)
