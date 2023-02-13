# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from testtools import TestCase

from maastesting.runtest import MAASRunTest, MAASTwistedRunTest


class TestExecutors:
    @pytest.mark.parametrize("executor", [MAASRunTest, MAASTwistedRunTest])
    def test_catches_generator_tests(self, executor):
        class BrokenTests(TestCase):
            run_tests_with = executor

            def test(self):
                yield None

        test = BrokenTests("test")
        result = test.run()

        assert len(result.errors) == 1
        failed_test, traceback = result.errors[0]
        assert failed_test is test
        assert (
            "InvalidTest: Test returned a generator. Should it be decorated with inlineCallbacks?"
            in str(traceback)
        )
