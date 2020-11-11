# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maastesting.runtest`."""


from testtools import TestCase
from testtools.matchers import HasLength, Is, MatchesListwise

from maastesting.matchers import DocTestMatches
from maastesting.runtest import MAASRunTest, MAASTwistedRunTest
from maastesting.testcase import MAASTestCase


class TestExecutors(MAASTestCase):
    """Tests for `MAASRunTest` and `MAASTwistedRunTest`."""

    scenarios = (
        ("MAASRunTest", {"executor": MAASRunTest}),
        ("MAASTwistedRunTest", {"executor": MAASTwistedRunTest}),
    )

    def test_catches_generator_tests(self):
        class BrokenTests(TestCase):

            run_tests_with = self.executor

            def test(self):
                yield None

        test = BrokenTests("test")
        result = test.run()

        self.assertThat(result.errors, HasLength(1))
        self.assertThat(
            result.errors[0],
            MatchesListwise(
                (
                    Is(test),
                    DocTestMatches(
                        """\
                ...InvalidTest:
                    Test returned a generator. Should it be
                    decorated with inlineCallbacks?
                """
                    ),
                )
            ),
        )
