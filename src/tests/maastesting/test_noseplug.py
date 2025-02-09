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
from twisted.python.filepath import FilePath

from maastesting import noseplug
from maastesting.factory import factory
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
        with_crochet, no_setup = parser.option_list[-2:]
        self.assertEqual(with_crochet.action, "store_true")
        self.assertIsNone(with_crochet.default)
        self.assertEqual(with_crochet.dest, "enable_plugin_crochet")
        self.assertEqual(no_setup.action, "store_true")
        self.assertFalse(no_setup.default)
        self.assertEqual(no_setup.dest, "crochet_no_setup")

    def test_configure_sets_up_crochet_if_enabled(self):
        self.patch_autospec(crochet_module, "setup")
        self.patch_autospec(crochet_module, "no_setup")

        crochet = Crochet()
        parser = OptionParser()
        crochet.add_options(parser=parser, env={})
        options, rest = parser.parse_args(["--with-crochet"])
        crochet.configure(options, sentinel.conf)

        crochet_module.setup.assert_called_once_with()
        crochet_module.no_setup.assert_not_called()

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

        crochet_module.setup.assert_not_called()
        crochet_module.no_setup.assert_called_once_with()

    def test_configure_does_not_set_up_crochet_if_not_enabled(self):
        self.patch_autospec(crochet_module, "setup")
        self.patch_autospec(crochet_module, "no_setup")

        crochet = Crochet()
        parser = OptionParser()
        crochet.add_options(parser=parser, env={})
        options, rest = parser.parse_args([])
        crochet.configure(options, sentinel.conf)

        crochet_module.setup.assert_not_called()
        crochet_module.no_setup.assert_not_called()


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

        self.assertEqual(len(list(suite)), 2)
        for sub_suite in list(suite):
            self.assertIsInstance(sub_suite, unittest.TestSuite)
        self.assertEqual(4, suite.countTestCases())

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        self.assertEqual(len(list(suite)), 4)
        for sub_case in list(suite):
            self.assertIsInstance(sub_case, unittest.TestCase)
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

        for sub_suite in list(suite):
            self.assertIsInstance(sub_suite, nose.case.Test)
        self.assertEqual(2, suite.countTestCases())
        self.assertEqual(
            {sentinel.notset},
            {getattr(test, "resources", sentinel.notset) for test in suite},
        )

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        # The test wrappers remain, but resources from the wrapped test are
        # now referenced from the wrapper so that testresources can see them.
        for sub_suite in list(suite):
            self.assertIsInstance(sub_suite, nose.case.Test)
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

        self.assertEqual(len(list(suite)), 1)
        for sub_suite in list(suite):
            self.assertIsInstance(sub_suite, unittest.TestSuite)
        self.assertEqual(2, suite.countTestCases())

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        # The nested suite is gone, the test wrappers remain, and resources
        # from the wrapped test are now referenced from the wrapper so that
        # testresources can see them.
        self.assertEqual(len(list(suite)), 2)
        for sub_suite in list(suite):
            self.assertIsInstance(sub_suite, nose.case.Test)
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

        self.assertEqual(len(tests), 2)
        for test in tests:
            self.assertIsInstance(test, SomeTests)
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

        self.assertEqual(len(tests), 4)
        for test in tests:
            self.assertIsInstance(test, SomeTests)
        self.assertEqual(
            {(test._testMethodName, test.attr) for test in tests},
            {("test_a", 1), ("test_a", 2), ("test_b", 1), ("test_b", 2)},
        )

    def test_makeTest_makes_tests_from_test_function(self):
        class SomeTests(MAASTestCase):
            def test_a(self):
                """Example test method."""

            def test_b(self):
                """Example test method."""

        method = random.choice((SomeTests.test_a, SomeTests.test_b))
        tests = self.makeTest(Scenarios(), method, SomeTests)

        self.assertEqual(len(tests), 1)
        for test in tests:
            self.assertIsInstance(test, SomeTests)
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

        self.assertEqual(len(tests), 2)
        for test in tests:
            self.assertIsInstance(test, SomeTests)
        self.assertEqual(
            {(method.__name__, 1), (method.__name__, 2)},
            {(test._testMethodName, test.attr) for test in tests},
        )


class TestSelect(MAASTestCase):
    def test_create_has_dirs(self):
        select = Select()
        self.assertEqual(select.dirs, frozenset())

    def test_options_adds_options(self):
        select = Select()
        parser = OptionParser()
        select.options(parser=parser, env={})
        with_select, select_dir = parser.option_list[-2:]
        self.assertEqual(with_select.action, "store_true")
        self.assertIsNone(with_select.default)
        self.assertEqual(with_select.dest, "enable_plugin_select")
        self.assertEqual(select_dir.action, "append")
        self.assertEqual(select_dir.default, [])
        self.assertEqual(select_dir.dest, "select_dirs")
        self.assertEqual(select_dir.metavar, "DIR")
        self.assertEqual(select_dir.type, "string")
        self.assertEqual(select_dir._short_opts, [])
        self.assertEqual(
            select_dir._long_opts, ["--select-dir", "--select-directory"]
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
        with_select_bucket, select_bucket = parser.option_list[-2:]
        self.assertEqual(with_select_bucket.action, "store_true")
        self.assertIsNone(with_select_bucket.default)
        self.assertEqual(
            with_select_bucket.dest, "enable_plugin_select_bucket"
        )
        self.assertEqual(select_bucket.action, "callback")
        self.assertIsNone(select_bucket.default)
        self.assertEqual(select_bucket.dest, "select-bucket_selected_bucket")
        self.assertEqual(select_bucket.metavar, "BUCKET/BUCKETS")
        self.assertEqual(select_bucket.type, "string")
        self.assertEqual(select_bucket._short_opts, [])
        self.assertEqual(select_bucket._long_opts, ["--select-bucket"])

    def test_configure_parses_selected_bucket(self):
        select = SelectBucket()
        parser = OptionParser()
        select.add_options(parser=parser, env={})
        options, rest = parser.parse_args(
            ["--with-select-bucket", "--select-bucket", "8/13"]
        )
        select.configure(options, sentinel.conf)
        self.assertTrue(callable(select._selectTest))

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
        with_subunit, subunit_fd = parser.option_list[-2:]
        self.assertEqual(with_subunit.action, "store_true")
        self.assertIsNone(with_subunit.default)
        self.assertEqual(with_subunit.dest, "enable_plugin_subunit")
        self.assertEqual(subunit_fd.action, "store")
        self.assertEqual(subunit_fd.default, 1)
        self.assertEqual(subunit_fd.dest, "subunit_fd")
        self.assertEqual(subunit_fd.metavar, "FD")
        self.assertEqual(subunit_fd.type, "int")
        self.assertEqual(subunit_fd._short_opts, [])
        self.assertEqual(subunit_fd._long_opts, ["--subunit-fd"])

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
            self.assertIs(result._stream, stream)


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
