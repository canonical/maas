# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from testtools import TestCase
from twisted.internet.error import ReactorAlreadyRunning

from maastesting.runtest import MAASRunTest, MAASTwistedRunTest


def assert_generator_caught(result, test):
    assert len(result.errors) == 1
    failed_test, traceback = result.errors[0]
    assert failed_test is test
    assert (
        "InvalidTest: Test returned a generator. Should it be decorated with inlineCallbacks?"
        in str(traceback)
    )


class TestExecutors:
    def test_catches_generator_tests_maasruntest(self):
        class BrokenTests(TestCase):
            run_tests_with = MAASRunTest

            def test(self):
                yield None

        test = BrokenTests("test")
        assert_generator_caught(test.run(), test)

    def test_catches_generator_tests_maastwistedruntest(self):
        """MAASTwistedRunTest should catch tests that return a generator.

        This executor runs the test inside the global Twisted reactor,
        which is only possible when the reactor is not already running.
        In the main test suite the reactor is managed by crochet for the
        whole session (maastesting.pytest.legacy's _crochet_reactor), so
        starting it again raises ReactorAlreadyRunning; skip in that
        case. The rack-legacy leg (MAAS_PYTEST_NO_CROCHET) keeps the
        process reactor free, so the test runs there.
        """

        class BrokenTests(TestCase):
            run_tests_with = MAASTwistedRunTest

            def test(self):
                yield None

        test = BrokenTests("test")
        try:
            result = test.run()
        except ReactorAlreadyRunning:
            pytest.skip(
                "the global Twisted reactor is already running (crochet)"
            )
        assert_generator_caught(result, test)
