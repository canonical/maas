# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import os
import random
from unittest.mock import ANY

import junitxml
import subunit
import testtools
from testtools import (
    ExtendedToOriginalDecorator,
    MultiTestResult,
    TextTestResult,
)
from testtools.matchers import (
    AfterPreprocessing,
    Is,
    IsInstance,
    MatchesAll,
    MatchesListwise,
    MatchesSetwise,
    MatchesStructure,
)

from maastesting import parallel
from maastesting.fixtures import CaptureStandardIO
from maastesting.matchers import (
    DocTestMatches,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase


class TestSelectorArguments(MAASTestCase):
    """Tests for arguments that select scripts."""

    def setUp(self):
        super().setUp()
        self.stdio = self.useFixture(CaptureStandardIO())
        self.patch_autospec(parallel, "test")
        parallel.test.return_value = True

    def assertScriptsMatch(self, *matchers):
        self.assertThat(parallel.test, MockCalledOnceWith(ANY, ANY, ANY))
        suite, results, processes = parallel.test.call_args[0]
        self.assertThat(
            suite, AfterPreprocessing(list, MatchesSetwise(*matchers))
        )

    def test_all_scripts_are_selected_when_no_selectors(self):
        sysexit = self.assertRaises(SystemExit, parallel.main, [])
        self.assertEqual(0, sysexit.code)
        self.assertScriptsMatch(
            MatchesUnselectableScript("bin/test.region.legacy"),
            MatchesSelectableScript("rack"),
            MatchesSelectableScript("region"),
        )

    def test_scripts_can_be_selected_by_path(self):
        sysexit = self.assertRaises(
            SystemExit,
            parallel.main,
            [
                "src/provisioningserver/002",
                "src/maasserver/003",
                "src/metadataserver/004",
            ],
        )
        self.assertEqual(0, sysexit.code)
        self.assertScriptsMatch(
            MatchesSelectableScript("rack", "src/provisioningserver/002"),
            MatchesSelectableScript(
                "region", "src/maasserver/003", "src/metadataserver/004"
            ),
        )

    def test_scripts_can_be_selected_by_module(self):
        sysexit = self.assertRaises(
            SystemExit,
            parallel.main,
            [
                "provisioningserver.002",
                "maasserver.003",
                "metadataserver.004",
            ],
        )
        self.assertEqual(0, sysexit.code)
        self.assertScriptsMatch(
            MatchesSelectableScript("rack", "provisioningserver.002"),
            MatchesSelectableScript(
                "region", "maasserver.003", "metadataserver.004"
            ),
        )


def MatchesUnselectableScript(what, *selectors):
    return MatchesAll(
        IsInstance(parallel.TestScriptUnselectable),
        MatchesStructure.byEquality(script=what),
        first_only=True,
    )


def MatchesSelectableScript(what, *selectors):
    return MatchesAll(
        IsInstance(parallel.TestScriptSelectable),
        MatchesStructure.byEquality(
            script="bin/test.%s" % what, selectors=selectors
        ),
        first_only=True,
    )


class TestSubprocessArguments(MAASTestCase):
    """Tests for arguments that adjust subprocess behaviour."""

    def setUp(self):
        super().setUp()
        self.stdio = self.useFixture(CaptureStandardIO())
        self.patch_autospec(parallel, "test")
        parallel.test.return_value = True

    def test_defaults(self):
        sysexit = self.assertRaises(SystemExit, parallel.main, [])
        self.assertEqual(0, sysexit.code)
        self.assertThat(
            parallel.test,
            MockCalledOnceWith(ANY, ANY, max(os.cpu_count() - 2, 2)),
        )

    def test_subprocess_count_can_be_specified(self):
        count = random.randrange(100, 1000)
        sysexit = self.assertRaises(
            SystemExit, parallel.main, ["--subprocesses", str(count)]
        )
        self.assertEqual(0, sysexit.code)
        self.assertThat(parallel.test, MockCalledOnceWith(ANY, ANY, count))

    def test_subprocess_count_of_less_than_1_is_rejected(self):
        sysexit = self.assertRaises(
            SystemExit, parallel.main, ["--subprocesses", "0"]
        )
        self.assertEqual(2, sysexit.code)
        self.assertThat(parallel.test, MockNotCalled())
        self.assertThat(
            self.stdio.getError(),
            DocTestMatches(
                "usage: ... argument --subprocesses: 0 is not 1 or greater"
            ),
        )

    def test_subprocess_count_non_numeric_is_rejected(self):
        sysexit = self.assertRaises(
            SystemExit, parallel.main, ["--subprocesses", "foo"]
        )
        self.assertEqual(2, sysexit.code)
        self.assertThat(parallel.test, MockNotCalled())
        self.assertThat(
            self.stdio.getError(),
            DocTestMatches(
                "usage: ... argument --subprocesses: 'foo' is not an integer"
            ),
        )

    def test_subprocess_per_core_can_be_specified(self):
        sysexit = self.assertRaises(
            SystemExit, parallel.main, ["--subprocess-per-core"]
        )
        self.assertEqual(0, sysexit.code)
        self.assertThat(
            parallel.test, MockCalledOnceWith(ANY, ANY, os.cpu_count())
        )

    def test_subprocess_count_and_per_core_cannot_both_be_specified(self):
        sysexit = self.assertRaises(
            SystemExit,
            parallel.main,
            ["--subprocesses", "3", "--subprocess-per-core"],
        )
        self.assertEqual(2, sysexit.code)
        self.assertThat(parallel.test, MockNotCalled())
        self.assertThat(
            self.stdio.getError(),
            DocTestMatches(
                "usage: ... argument --subprocess-per-core: not allowed with "
                "argument --subprocesses"
            ),
        )


class TestEmissionArguments(MAASTestCase):
    """Tests for arguments that adjust result emission behaviour."""

    def setUp(self):
        super().setUp()
        self.stdio = self.useFixture(CaptureStandardIO())
        self.patch_autospec(parallel, "test")
        parallel.test.return_value = True

    def test_results_are_human_readable_by_default(self):
        sysexit = self.assertRaises(SystemExit, parallel.main, [])
        self.assertEqual(0, sysexit.code)
        self.assertThat(parallel.test, MockCalledOnceWith(ANY, ANY, ANY))
        _, result, _ = parallel.test.call_args[0]
        self.assertThat(
            result,
            IsMultiResultOf(
                IsInstance(TextTestResult),
                IsInstance(testtools.TestByTestResult),
            ),
        )

    def test_results_can_be_explicitly_specified_as_human_readable(self):
        sysexit = self.assertRaises(
            SystemExit, parallel.main, ["--emit-human"]
        )
        self.assertEqual(0, sysexit.code)
        self.assertThat(parallel.test, MockCalledOnceWith(ANY, ANY, ANY))
        _, result, _ = parallel.test.call_args[0]
        self.assertThat(
            result,
            IsMultiResultOf(
                IsInstance(TextTestResult),
                IsInstance(testtools.TestByTestResult),
            ),
        )

    def test_results_can_be_specified_as_subunit(self):
        sysexit = self.assertRaises(
            SystemExit, parallel.main, ["--emit-subunit"]
        )
        self.assertEqual(0, sysexit.code)
        self.assertThat(parallel.test, MockCalledOnceWith(ANY, ANY, ANY))
        _, result, _ = parallel.test.call_args[0]
        self.assertIsInstance(result, subunit.TestProtocolClient)
        self.assertThat(
            result, MatchesStructure(_stream=Is(self.stdio.stdout.buffer))
        )

    def test_results_can_be_specified_as_junit(self):
        sysexit = self.assertRaises(
            SystemExit, parallel.main, ["--emit-junit"]
        )
        self.assertEqual(0, sysexit.code)
        self.assertThat(parallel.test, MockCalledOnceWith(ANY, ANY, ANY))
        _, result, _ = parallel.test.call_args[0]
        self.assertIsInstance(result, junitxml.JUnitXmlResult)
        self.assertThat(
            result, MatchesStructure(_stream=Is(self.stdio.stdout))
        )


def IsMultiResultOf(*results):
    """Match a `MultiTestResult` wrapping the given results."""
    return MatchesAll(
        IsInstance(MultiTestResult),
        MatchesStructure(
            _results=MatchesListwise(
                [
                    MatchesAll(
                        IsInstance(ExtendedToOriginalDecorator),
                        MatchesStructure(decorated=matcher),
                        first_only=True,
                    )
                    for matcher in results
                ]
            )
        ),
        first_only=True,
    )
