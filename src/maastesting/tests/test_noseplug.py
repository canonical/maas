# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maastesting.noseplug`."""

__all__ = []

from optparse import OptionParser
from os import makedirs
from os.path import (
    dirname,
    join,
)
import random
import unittest
from unittest.mock import (
    ANY,
    sentinel,
)

import crochet as crochet_module
from maastesting import noseplug
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.noseplug import (
    Crochet,
    Resources,
    Scenarios,
    Select,
)
from maastesting.testcase import MAASTestCase
import nose.case
from testresources import OptimisingTestSuite
from testtools.matchers import (
    AllMatch,
    Equals,
    HasLength,
    IsInstance,
    MatchesListwise,
    MatchesSetwise,
    MatchesStructure,
    Not,
)
from twisted.python.filepath import FilePath


class TestCrochet(MAASTestCase):

    def test__options_adds_options(self):
        crochet = Crochet()
        parser = OptionParser()
        crochet.options(parser=parser, env={})
        self.assertThat(
            parser.option_list[-2:],
            MatchesListwise([
                # The --with-crochet option.
                MatchesStructure.byEquality(
                    action="store_true", default=None,
                    dest="enable_plugin_crochet",
                ),
                # The --crochet-no-setup option.
                MatchesStructure.byEquality(
                    action="store_true", default=False,
                    dest="crochet_no_setup",
                ),
            ]))

    def test__configure_sets_up_crochet_if_enabled(self):
        self.patch_autospec(crochet_module, "setup")
        self.patch_autospec(crochet_module, "no_setup")

        crochet = Crochet()
        parser = OptionParser()
        crochet.add_options(parser=parser, env={})
        options, rest = parser.parse_args(["--with-crochet"])
        crochet.configure(options, sentinel.conf)

        self.assertThat(crochet_module.setup, MockCalledOnceWith())
        self.assertThat(crochet_module.no_setup, MockNotCalled())

    def test__configure_sets_up_crochet_with_no_setup_if_enabled(self):
        self.patch_autospec(crochet_module, "setup")
        self.patch_autospec(crochet_module, "no_setup")

        crochet = Crochet()
        parser = OptionParser()
        crochet.add_options(parser=parser, env={})
        options, rest = parser.parse_args(
            ["--with-crochet", "--crochet-no-setup"])
        crochet.configure(options, sentinel.conf)

        self.assertThat(crochet_module.setup, MockNotCalled())
        self.assertThat(crochet_module.no_setup, MockCalledOnceWith())

    def test__configure_does_not_set_up_crochet_if_not_enabled(self):
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
            test_a = lambda self: None
            test_b = lambda self: None

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(SomeTests)
        self.assertThat(suite, Not(IsInstance(OptimisingTestSuite)))
        self.assertThat(suite.countTestCases(), Equals(2))

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        self.assertThat(suite, IsInstance(OptimisingTestSuite))
        self.assertThat(suite.countTestCases(), Equals(2))

    def test_prepareTest_flattens_nested_suites(self):

        class SomeTests(MAASTestCase):
            test_a = lambda self: None
            test_b = lambda self: None

        class MoreTests(MAASTestCase):
            test_c = lambda self: None
            test_d = lambda self: None

        loader = unittest.TestLoader()
        suite = unittest.TestSuite([
            loader.loadTestsFromTestCase(SomeTests),
            loader.loadTestsFromTestCase(MoreTests),
        ])

        self.assertThat(list(suite), HasLength(2))
        self.assertThat(list(suite), AllMatch(IsInstance(unittest.TestSuite)))
        self.assertThat(suite.countTestCases(), Equals(4))

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        self.assertThat(list(suite), HasLength(4))
        self.assertThat(list(suite), AllMatch(IsInstance(unittest.TestCase)))
        self.assertThat(suite.countTestCases(), Equals(4))

    def test_prepareTest_hoists_resources(self):

        class SomeTests(MAASTestCase):
            resources = sentinel.resources
            test_a = lambda self: None
            test_b = lambda self: None

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(SomeTests)
        # Nose wraps each test in another test to make our lives miserable.
        suite = unittest.TestSuite(map(nose.case.Test, suite))

        self.assertThat(list(suite), AllMatch(IsInstance(nose.case.Test)))
        self.assertThat(suite.countTestCases(), Equals(2))
        self.assertThat(
            {getattr(test, "resources", sentinel.notset) for test in suite},
            Equals({sentinel.notset}))

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        # The test wrappers remain, but resources from the wrapped test are
        # now referenced from the wrapper so that testresources can see them.
        self.assertThat(list(suite), AllMatch(IsInstance(nose.case.Test)))
        self.assertThat(suite.countTestCases(), Equals(2))
        self.assertThat(
            {getattr(test, "resources", sentinel.notset) for test in suite},
            Equals({SomeTests.resources}))

    def test_prepareTest_hoists_resources_of_nested_tests(self):

        class SomeTests(MAASTestCase):
            resources = sentinel.resources
            test_a = lambda self: None
            test_b = lambda self: None

        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(SomeTests)
        # Nose wraps each test in another test to make our lives miserable.
        suite = unittest.TestSuite(map(nose.case.Test, suite))
        # Nest this suite within another.
        suite = unittest.TestSuite([suite])

        self.assertThat(list(suite), HasLength(1))
        self.assertThat(list(suite), AllMatch(IsInstance(unittest.TestSuite)))
        self.assertThat(suite.countTestCases(), Equals(2))

        plugin = Resources()
        suite = plugin.prepareTest(suite)

        # The nested suite is gone, the test wrappers remain, and resources
        # from the wrapped test are now referenced from the wrapper so that
        # testresources can see them.
        self.assertThat(list(suite), HasLength(2))
        self.assertThat(list(suite), AllMatch(IsInstance(nose.case.Test)))
        self.assertThat(suite.countTestCases(), Equals(2))
        self.assertThat(
            {getattr(test, "resources", sentinel.notset) for test in suite},
            Equals({SomeTests.resources}))


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
            test_a = lambda self: None
            test_b = lambda self: None

        tests = self.makeTest(Scenarios(), SomeTests, self)

        self.assertThat(tests, HasLength(2))
        self.assertThat(tests, AllMatch(IsInstance(SomeTests)))
        self.assertThat(
            {test._testMethodName for test in tests},
            Equals({"test_a", "test_b"}))

    def test_makeTest_makes_tests_from_test_case_class_with_scenarios(self):

        class SomeTests(MAASTestCase):
            scenarios = [("scn1", {"attr": 1}), ("scn2", {"attr": 2})]
            test_a = lambda self: None
            test_b = lambda self: None

        tests = self.makeTest(Scenarios(), SomeTests, self)

        self.assertThat(tests, HasLength(4))
        self.assertThat(tests, AllMatch(IsInstance(SomeTests)))
        self.assertThat(
            {(test._testMethodName, test.attr) for test in tests},
            Equals({
                ("test_a", 1), ("test_a", 2),
                ("test_b", 1), ("test_b", 2),
            }))

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
        self.assertThat(
            {test._testMethodName for test in tests},
            Equals({method.__name__}))

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
        self.assertThat(
            {(test._testMethodName, test.attr) for test in tests},
            Equals({(method.__name__, 1), (method.__name__, 2)}))


class TestSelect(MAASTestCase):

    def test__create_has_dirs(self):
        select = Select()
        self.assertThat(
            select, MatchesStructure.byEquality(dirs=frozenset()))

    def test__options_adds_options(self):
        select = Select()
        parser = OptionParser()
        select.options(parser=parser, env={})
        self.assertThat(
            parser.option_list[-2:],
            MatchesListwise([
                # The --with-select option.
                MatchesStructure.byEquality(
                    action="store_true", default=None,
                    dest="enable_plugin_select",
                ),
                # The --select-dir/--select-directory option.
                MatchesStructure.byEquality(
                    action="append", default=[], dest="select_dirs",
                    metavar="DIR", type="string", _short_opts=[],
                    _long_opts=["--select-dir", "--select-directory"],
                )
            ]))

    def test__configure_scans_directories(self):
        directory = self.make_dir()
        segments = factory.make_name("child"), factory.make_name("grandchild")
        makedirs(join(directory, *segments))

        select = Select()
        parser = OptionParser()
        select.add_options(parser=parser, env={})
        options, rest = parser.parse_args(
            ["--with-select", "--select-dir", directory])
        select.configure(options, sentinel.conf)

        leaf = FilePath(directory).descendant(segments)
        expected_dirs = {leaf}
        expected_dirs.update(leaf.parents())
        self.assertThat(select.dirs, Equals(
            set(fp.path for fp in expected_dirs)))

    def test__wantDirectory_checks_dirs_and_thats_it(self):
        directory = self.make_dir()
        segments = factory.make_name("child"), factory.make_name("grandchild")
        makedirs(join(directory, *segments))

        select = Select()
        self.assertFalse(select.wantDirectory(directory))
        select.addDirectory(directory)
        self.assertTrue(select.wantDirectory(directory))
        self.assertTrue(select.wantDirectory(join(directory, *segments)))
        self.assertTrue(select.wantDirectory(dirname(directory)))
        self.assertFalse(select.wantDirectory(
            join(directory, factory.make_name("other-child"))))


class TestMain(MAASTestCase):

    def test__sets_addplugins(self):
        self.patch(noseplug, "TestProgram")
        noseplug.main()
        self.assertThat(
            noseplug.TestProgram,
            MockCalledOnceWith(addplugins=(ANY, ANY, ANY, ANY)))
        plugins = noseplug.TestProgram.call_args[1]["addplugins"]
        self.assertThat(plugins, MatchesSetwise(
            IsInstance(Crochet), IsInstance(Resources),
            IsInstance(Scenarios), IsInstance(Select),
        ))
