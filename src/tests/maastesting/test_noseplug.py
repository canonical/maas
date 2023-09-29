# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maastesting.noseplug`."""


from optparse import OptionParser
from os import devnull, makedirs
from os.path import dirname, join
import random
import unittest
from unittest.mock import sentinel

import crochet as crochet_module
import nose.case
import subunit
from testresources import OptimisingTestSuite
from testtools.matchers import (
    AllMatch,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesListwise,
    MatchesStructure,
)
from twisted.python.filepath import FilePath

from maastesting import noseplug
from maastesting.factory import factory
from maastesting.matchers import IsCallable, MockCalledOnceWith, MockNotCalled
from maastesting.noseplug import (
    CleanTestToolsFailure,
    Crochet,
    Resources,
    Scenarios,
    Select,
    SelectBucket,
    Subunit,
)
from maastesting.testcase import MAASTestCase


class TestCrochet(MAASTestCase):
    def test_options_adds_options(self):
        crochet = Crochet()
        parser = OptionParser()
        crochet.options(parser=parser, env={})
        self.assertThat(
            parser.option_list[-2:],
            MatchesListwise(
                [
                    # The --with-crochet option.
                    MatchesStructure.byEquality(
                        action="store_true",
                        default=None,
                        dest="enable_plugin_crochet",
                    ),
                    # The --crochet-no-setup option.
                    MatchesStructure.byEquality(
                        action="store_true",
                        default=False,
                        dest="crochet_no_setup",
                    ),
                ]
            ),
        )

    def test_configure_sets_up_crochet_if_enabled(self):
        self.patch_autospec(crochet_module, "setup")
        self.patch_autospec(crochet_module, "no_setup")

        crochet = Crochet()
        parser = OptionParser()
        crochet.add_options(parser=parser, env={})
        options, rest = parser.parse_args(["--with-crochet"])
        crochet.configure(options, sentinel.conf)

        self.assertThat(crochet_module.setup, MockCalledOnceWith())
        self.assertThat(crochet_module.no_setup, MockNotCalled())

    def test_configure_sets_up_crochet_with_no_setup_if_enabled(self):
        self.patch_autospec(crochet_module, "setup")
        self.patch_autospec(crochet_module, "no_setup")

        crochet = Crochet()
        parser = OptionParser()
        crochet.add_options(parser=parser, env={})
        options, rest = parser.parse_args(
            ["--with-crochet", "--crochet-no-setup"]
        )
        crochet.configure(options, sentinel.conf)

        self.assertThat(crochet_module.setup, MockNotCalled())
        self.assertThat(crochet_module.no_setup, MockCalledOnceWith())

    def test_configure_does_not_set_up_crochet_if_not_enabled(self):
        self.patch_autospec(crochet_module, "setup")
        self.patch_autospec(crochet_module, "no_setup")

        crochet = Crochet()
        parser = OptionParser()
        crochet.add_options(parser=parser, env={})
        options, rest = parser.parse_args([])
        crochet.configure(options, sentinel.conf)

        self.assertThat(crochet_module.setup, MockNotCalled())
        self.assertThat(crochet_module.no_setup, MockNotCalled())


class TestResources(MAASTestCase):
    def test_prepareTest_returns_optimised_test_suite(self):
        class SomeTests(MAASTestCase):
            def test_a(self):
                pass

            def test_b(self):
                pass

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(SomeTests)
        self.assertNotIsInstance(suite, OptimisingTestSuite)
        self.assertEqual(2, suite.countTestCases())

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        self.assertIsInstance(suite, OptimisingTestSuite)
        self.assertEqual(2, suite.countTestCases())

    def test_prepareTest_flattens_nested_suites(self):
        class SomeTests(MAASTestCase):
            def test_a(self):
                pass

            def test_b(self):
                pass

        class MoreTests(MAASTestCase):
            def test_c(self):
                pass

            def test_d(self):
                pass

        loader = unittest.TestLoader()
        suite = unittest.TestSuite(
            [
                loader.loadTestsFromTestCase(SomeTests),
                loader.loadTestsFromTestCase(MoreTests),
            ]
        )

        self.assertThat(list(suite), HasLength(2))
        self.assertThat(list(suite), AllMatch(IsInstance(unittest.TestSuite)))
        self.assertEqual(4, suite.countTestCases())

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        self.assertThat(list(suite), HasLength(4))
        self.assertThat(list(suite), AllMatch(IsInstance(unittest.TestCase)))
        self.assertEqual(4, suite.countTestCases())

    def test_prepareTest_hoists_resources(self):
        class SomeTests(MAASTestCase):
            resources = sentinel.resources

            def test_a(self):
                pass

            def test_b(self):
                pass

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(SomeTests)
        # Nose wraps each test in another test to make our lives miserable.
        suite = unittest.TestSuite(map(nose.case.Test, suite))

        self.assertThat(list(suite), AllMatch(IsInstance(nose.case.Test)))
        self.assertEqual(2, suite.countTestCases())
        self.assertEqual(
            {sentinel.notset},
            {getattr(test, "resources", sentinel.notset) for test in suite},
        )

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        # The test wrappers remain, but resources from the wrapped test are
        # now referenced from the wrapper so that testresources can see them.
        self.assertThat(list(suite), AllMatch(IsInstance(nose.case.Test)))
        self.assertEqual(2, suite.countTestCases())
        self.assertEqual(
            {SomeTests.resources},
            {getattr(test, "resources", sentinel.notset) for test in suite},
        )

    def test_prepareTest_hoists_resources_of_nested_tests(self):
        class SomeTests(MAASTestCase):
            resources = sentinel.resources

            def test_a(self):
                pass

            def test_b(self):
                pass

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(SomeTests)
        # Nose wraps each test in another test to make our lives miserable.
        suite = unittest.TestSuite(map(nose.case.Test, suite))
        # Nest this suite within another.
        suite = unittest.TestSuite([suite])

        self.assertThat(list(suite), HasLength(1))
        self.assertThat(list(suite), AllMatch(IsInstance(unittest.TestSuite)))
        self.assertEqual(2, suite.countTestCases())

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        # The nested suite is gone, the test wrappers remain, and resources
        # from the wrapped test are now referenced from the wrapper so that
        # testresources can see them.
        self.assertThat(list(suite), HasLength(2))
        self.assertThat(list(suite), AllMatch(IsInstance(nose.case.Test)))
        self.assertEqual(2, suite.countTestCases())
        self.assertEqual(
            {SomeTests.resources},
            {getattr(test, "resources", sentinel.notset) for test in suite},
        )


class TestScenarios(MAASTestCase):
    @staticmethod
    def makeTest(plugin, obj, parent):
        # Call the plugin via an intermediate function where we can create a
        # test loader and call it `self`; the Scenarios plugin walks the stack
        # to find it.
        self = unittest.TestLoader()  # noqa
        tests = plugin.makeTest(obj, parent)
        return list(tests)

    def test_makeTest_makes_tests_from_test_case_class(self):
        class SomeTests(MAASTestCase):
            def test_a(self):
                pass

            def test_b(self):
                pass

        tests = self.makeTest(Scenarios(), SomeTests, self)

        self.assertThat(tests, HasLength(2))
        self.assertThat(tests, AllMatch(IsInstance(SomeTests)))
        self.assertEqual(
            {"test_a", "test_b"},
            {test._testMethodName for test in tests},
        )

    def test_makeTest_makes_tests_from_test_case_class_with_scenarios(self):
        class SomeTests(MAASTestCase):
            scenarios = [("scn1", {"attr": 1}), ("scn2", {"attr": 2})]

            def test_a(self):
                pass

            def test_b(self):
                pass

        tests = self.makeTest(Scenarios(), SomeTests, self)

        self.assertThat(tests, HasLength(4))
        self.assertThat(tests, AllMatch(IsInstance(SomeTests)))
        self.assertThat(
            {(test._testMethodName, test.attr) for test in tests},
            Equals(
                {("test_a", 1), ("test_a", 2), ("test_b", 1), ("test_b", 2)}
            ),
        )

    def test_makeTest_makes_tests_from_test_function(self):
        class SomeTests(MAASTestCase):
            def test_a(self):
                """Example test method."""

            def test_b(self):
                """Example test method."""

        method = random.choice((SomeTests.test_a, SomeTests.test_b))
        tests = self.makeTest(Scenarios(), method, SomeTests)

        self.assertThat(tests, HasLength(1))
        self.assertThat(tests, AllMatch(IsInstance(SomeTests)))
        self.assertEqual(
            {method.__name__}, {test._testMethodName for test in tests}
        )

    def test_makeTest_makes_tests_from_test_function_with_scenarios(self):
        class SomeTests(MAASTestCase):
            scenarios = [("scn1", {"attr": 1}), ("scn2", {"attr": 2})]

            def test_a(self):
                """Example test method."""

            def test_b(self):
                """Example test method."""

        method = random.choice((SomeTests.test_a, SomeTests.test_b))
        tests = self.makeTest(Scenarios(), method, SomeTests)

        self.assertThat(tests, HasLength(2))
        self.assertThat(tests, AllMatch(IsInstance(SomeTests)))
        self.assertEqual(
            {(method.__name__, 1), (method.__name__, 2)},
            {(test._testMethodName, test.attr) for test in tests},
        )


class TestSelect(MAASTestCase):
    def test_create_has_dirs(self):
        select = Select()
        self.assertThat(select, MatchesStructure.byEquality(dirs=frozenset()))

    def test_options_adds_options(self):
        select = Select()
        parser = OptionParser()
        select.options(parser=parser, env={})
        self.assertThat(
            parser.option_list[-2:],
            MatchesListwise(
                [
                    # The --with-select option.
                    MatchesStructure.byEquality(
                        action="store_true",
                        default=None,
                        dest="enable_plugin_select",
                    ),
                    # The --select-dir/--select-directory option.
                    MatchesStructure.byEquality(
                        action="append",
                        default=[],
                        dest="select_dirs",
                        metavar="DIR",
                        type="string",
                        _short_opts=[],
                        _long_opts=["--select-dir", "--select-directory"],
                    ),
                ]
            ),
        )

    def test_configure_scans_directories(self):
        directory = self.make_dir()
        segments = factory.make_name("child"), factory.make_name("grandchild")
        makedirs(join(directory, *segments))

        select = Select()
        parser = OptionParser()
        select.add_options(parser=parser, env={})
        options, rest = parser.parse_args(
            ["--with-select", "--select-dir", directory]
        )
        select.configure(options, sentinel.conf)

        leaf = FilePath(directory).descendant(segments)
        expected_dirs = {leaf}
        expected_dirs.update(leaf.parents())
        self.assertEqual({fp.path for fp in expected_dirs}, select.dirs)

    def test_wantDirectory_checks_dirs_and_thats_it(self):
        directory = self.make_dir()
        segments = factory.make_name("child"), factory.make_name("grandchild")
        makedirs(join(directory, *segments))

        select = Select()
        self.assertFalse(select.wantDirectory(directory))
        select.addDirectory(directory)
        self.assertTrue(select.wantDirectory(directory))
        self.assertTrue(select.wantDirectory(join(directory, *segments)))
        self.assertTrue(select.wantDirectory(dirname(directory)))
        self.assertFalse(
            select.wantDirectory(
                join(directory, factory.make_name("other-child"))
            )
        )


class TestSelectBucket(MAASTestCase):
    def test_options_adds_options(self):
        select = SelectBucket()
        parser = OptionParser()
        select.options(parser=parser, env={})
        self.assertThat(
            parser.option_list[-2:],
            MatchesListwise(
                [
                    # The --with-select-bucket option.
                    MatchesStructure.byEquality(
                        action="store_true",
                        default=None,
                        dest="enable_plugin_select_bucket",
                    ),
                    # The --select-bucket option.
                    MatchesStructure.byEquality(
                        action="callback",
                        default=None,
                        dest="select-bucket_selected_bucket",
                        metavar="BUCKET/BUCKETS",
                        type="string",
                        _short_opts=[],
                        _long_opts=["--select-bucket"],
                    ),
                ]
            ),
        )

    def test_configure_parses_selected_bucket(self):
        select = SelectBucket()
        parser = OptionParser()
        select.add_options(parser=parser, env={})
        options, rest = parser.parse_args(
            ["--with-select-bucket", "--select-bucket", "8/13"]
        )
        select.configure(options, sentinel.conf)
        self.assertThat(select, MatchesStructure(_selectTest=IsCallable()))

    @staticmethod
    def _make_test_with_id(test_id):
        test = unittest.TestCase()
        test.id = lambda: test_id
        return test

    def test_prepareTestRunner_wraps_given_runner_and_filters_tests(self):
        select = SelectBucket()
        parser = OptionParser()
        select.add_options(parser=parser, env={})
        options, rest = parser.parse_args(
            ["--with-select-bucket", "--select-bucket", "8/13"]
        )
        select.configure(options, sentinel.conf)

        # We start at 65 because chr(65) is "A" and so makes a nice readable
        # ID for the test. We end at 77 because chr(77) is "M", a readable ID
        # once again, but more importantly it means we'll have 13 tests, which
        # is the modulus we started with.
        tests = map(self._make_test_with_id, map(chr, range(65, 78)))
        test = unittest.TestSuite(tests)
        self.assertEqual(13, test.countTestCases())

        class MockTestRunner:
            def run(self, test):
                self.test = test

        runner = runner_orig = MockTestRunner()
        runner = select.prepareTestRunner(runner)
        self.assertIsInstance(runner, noseplug.SelectiveTestRunner)

        runner.run(test)

        self.assertIsInstance(runner_orig.test, type(test))
        self.assertEqual(1, runner_orig.test.countTestCases())
        # Note how the test with ID of "H" is the only one selected.
        self.assertEqual({"H"}, {t.id() for t in runner_orig.test})
        self.assertEqual(7, ord("H") % 13)

    def test_prepareTestRunner_does_nothing_when_no_bucket_selected(self):
        select = SelectBucket()
        parser = OptionParser()
        select.add_options(parser=parser, env={})
        options, rest = parser.parse_args(["--with-select-bucket"])
        select.configure(options, sentinel.conf)
        self.assertIsNone(select.prepareTestRunner(sentinel.runner))


class TestSubunit(MAASTestCase):
    def test_options_adds_options(self):
        select = Subunit()
        parser = OptionParser()
        select.options(parser=parser, env={})
        self.assertThat(
            parser.option_list[-2:],
            MatchesListwise(
                [
                    # The --with-subunit option.
                    MatchesStructure.byEquality(
                        action="store_true",
                        default=None,
                        dest="enable_plugin_subunit",
                    ),
                    # The --subunit-fd option.
                    MatchesStructure.byEquality(
                        action="store",
                        default=1,
                        dest="subunit_fd",
                        metavar="FD",
                        type="int",
                        _short_opts=[],
                        _long_opts=["--subunit-fd"],
                    ),
                ]
            ),
        )

    def test_configure_opens_stream(self):
        subunit = Subunit()
        parser = OptionParser()
        subunit.add_options(parser=parser, env={})
        with open(devnull, "wb") as fd:
            options, rest = parser.parse_args(
                ["--with-subunit", "--subunit-fd", str(fd.fileno())]
            )
            subunit.configure(options, sentinel.conf)
            self.assertEqual(fd.fileno(), subunit.stream.fileno())
            self.assertEqual("wb", subunit.stream.mode)

    def test_prepareTestResult_returns_subunit_client(self):
        subunit_plugin = Subunit()
        with open(devnull, "wb") as stream:
            subunit_plugin.stream = stream
            result = subunit_plugin.prepareTestResult(sentinel.result)
            self.assertIsInstance(result, subunit.TestProtocolClient)
            self.assertThat(result, MatchesStructure(_stream=Is(stream)))


class TestMain(MAASTestCase):
    def test_sets_addplugins(self):
        self.patch(noseplug, "TestProgram")
        noseplug.main()
        noseplug.TestProgram.assert_called_once()
        plugin_classes = {
            plugin.__class__
            for plugin in noseplug.TestProgram.call_args[1]["addplugins"]
        }
        self.assertEqual(
            plugin_classes,
            {
                CleanTestToolsFailure,
                Crochet,
                Resources,
                Scenarios,
                Select,
                SelectBucket,
                Subunit,
            },
        )
