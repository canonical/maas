# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from itertools import islice

from hypothesis import given
from hypothesis.strategies import floats

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

    def test_full_jitter(self):
        # Test with various input values
        values = [10.0, 100.0, 1000.0]
        jittered = list(full_jitter(values))

        self.assertEqual(len(jittered), len(values))
        for original, jittered_value in zip(values, jittered, strict=True):
            self.assertIsInstance(jittered_value, float)
            self.assertGreaterEqual(jittered_value, 0.0)
            self.assertLess(jittered_value, original)

        # Test with empty list
        self.assertEqual(list(full_jitter([])), [])

        # Test with zero - should always produce zero
        self.assertEqual(list(full_jitter([0.0])), [0.0])
