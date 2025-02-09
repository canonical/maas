# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Nose plugins for MAAS."""

import inspect
import logging
import optparse
import sys
import unittest

from nose.case import Test
from nose.core import TestProgram
from nose.plugins.base import Plugin
from testresources import OptimisingTestSuite
from testscenarios import generate_scenarios
from testtools.testresult.real import _StringException
from twisted.python.filepath import FilePath


def flattenTests(tests):
    """Recursively eliminate nested test suites.

    A `TestSuite` can contain zero or more tests or other suites, or a mix of
    both. This function undoes all of this nesting. Be sure you know what you
    intend when doing this, because any behaviour that is endowed by those
    nested test suites will be lost.
    """
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            yield from flattenTests(test)
        else:
            yield test


class Crochet(Plugin):
    """Start the Twisted reactor via Crochet."""

    name = "crochet"
    option_no_setup = "%s_no_setup" % name
    log = logging.getLogger("nose.plugins.%s" % name)

    def options(self, parser, env):
        """Add options to Nose's parser.

        :attention: This is part of the Nose plugin contract.
        """
        super().options(parser, env)
        parser.add_option(
            "--%s-no-setup" % self.name,
            dest=self.option_no_setup,
            action="store_true",
            default=False,
            help="Initialize the crochet library with no side effects.",
        )

    def configure(self, options, conf):
        """Configure, based on the parsed options.

        :attention: This is part of the Nose plugin contract.
        """
        super().configure(options, conf)
        if self.enabled:
            import crochet

            # Remove deprecated crochet APIs.
            if hasattr(crochet, "wait_for_reactor"):
                del crochet.wait_for_reactor
            if hasattr(crochet.EventLoop, "wait_for_reactor"):
                del crochet.EventLoop.wait_for_reactor
            if hasattr(crochet, "DeferredResult"):
                del crochet.DeferredResult

            # Make a default timeout forbidden.
            class EventualResult(crochet.EventualResult):
                def _result(self, timeout=None):
                    if timeout is None:
                        raise AssertionError("A time-out must be specified.")
                    else:
                        return super()._result(timeout)

            # Patch it back into crochet.
            crochet._eventloop.EventualResult = EventualResult
            crochet.EventualResult = EventualResult

            if getattr(options, self.option_no_setup):
                crochet.no_setup()
            else:
                crochet.setup()

    def help(self):
        """Used in the --help text.

        :attention: This is part of the Nose plugin contract.
        """
        return inspect.getdoc(self)


class Resources(Plugin):
    """Optimise the use of test resources."""

    name = "resources"
    log = logging.getLogger("nose.plugins.%s" % name)

    def prepareTest(self, test):
        """Convert the test suite gathered by Nose.

        :return: An instance of :class:`OptimisingTestSuite`.
        """
        tests = flattenTests(test)
        tests = map(self._hoistResources, tests)
        return OptimisingTestSuite(tests)

    def _hoistResources(self, test):
        """Hoist resources from the real test to Nose's test wrapper."""
        if isinstance(test, Test):
            try:
                resources = test.test.resources
            except AttributeError:
                pass  # Test has no resources.
            else:
                test.resources = resources
        return test

    def help(self):
        """Used in the --help text.

        :attention: This is part of the Nose plugin contract.
        """
        return inspect.getdoc(self)


class Scenarios(Plugin):
    """Expand test scenarios so that they're visible to Nose."""

    name = "scenarios"
    log = logging.getLogger("nose.plugins.%s" % name)

    def makeTest(self, obj, parent):
        """Attempt to expand test scenarios in the given test or tests.

        If `obj` is a test case class, this loads tests and expands scenarios.

        If `parent` is a test case class, this assumes that `obj` is a method,
        instantiates the test case, then expands scenarios.

        Everything else is ignored so the loader that invoked this will revert
        to its default behaviour.
        """
        # obj may be a test case class.
        if isinstance(obj, type):
            if issubclass(obj, unittest.TestCase):
                loader = self._getTestLoader()
                tests = loader.loadTestsFromTestCase(obj)
                tests = map(self._unwrapTest, tests)
                return generate_scenarios(tests)
        # obj may be a function/method.
        elif isinstance(parent, type):
            if issubclass(parent, unittest.TestCase):
                test = parent(obj.__name__)
                return generate_scenarios(test)

    def _getTestLoader(self):
        """Return the currently active test loader.

        The loader may have non-default configuration, so we ought to reuse it
        rather than create a default loader. Sadly this involves walking the
        stack.
        """
        stack = inspect.stack()
        for info in stack[2:]:
            f_self = info.frame.f_locals.get("self")
            if isinstance(f_self, unittest.TestLoader):
                return f_self
        else:
            return None

    def _unwrapTest(self, test):
        """Remove Nose's annoying wrapper."""
        return test.test if isinstance(test, Test) else test

    def help(self):
        """Used in the --help text.

        :attention: This is part of the Nose plugin contract.
        """
        return inspect.getdoc(self)


class Select(Plugin):
    """Another way to limit which tests are chosen."""

    name = "select"
    option_dirs = "%s_dirs" % name
    log = logging.getLogger("nose.plugins.%s" % name)

    def __init__(self):
        super().__init__()
        self.dirs = frozenset()

    def options(self, parser, env):
        """Add options to Nose's parser.

        :attention: This is part of the Nose plugin contract.
        """
        super().options(parser, env)
        parser.add_option(
            "--%s-dir" % self.name,
            "--%s-directory" % self.name,
            dest=self.option_dirs,
            action="append",
            default=[],
            help=(
                "Allow test discovery in this directory. Explicitly named "
                "tests outside of this directory may still be loaded. This "
                "option can be given multiple times to allow discovery in "
                "multiple directories."
            ),
            metavar="DIR",
        )

    def configure(self, options, conf):
        """Configure, based on the parsed options.

        :attention: This is part of the Nose plugin contract.
        """
        super().configure(options, conf)
        if self.enabled:
            # Process --${name}-dir.
            for path in getattr(options, self.option_dirs):
                self.addDirectory(path)
            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug(
                    "Limiting to the following directories "
                    "(exact matches only):"
                )
                for path in sorted(self.dirs):
                    self.log.debug("- %s", path)

    def addDirectory(self, path):
        """Include `path` in test discovery.

        This scans all child directories of `path` and also all `parents`;
        `wantDirectory()` can then do an exact match.
        """
        start = FilePath(path)
        self.dirs = self.dirs.union(
            (fp.path for fp in start.parents()),
            (fp.path for fp in start.walk() if fp.isdir()),
        )

    def wantDirectory(self, path):
        """Rejects directories outside of the chosen few.

        :attention: This is part of the Nose plugin contract.
        """
        if path in self.dirs:
            self.log.debug("Selecting %s", path)
            return True
        else:
            self.log.debug("Rejecting %s", path)
            return False

    def help(self):
        """Used in the --help text.

        :attention: This is part of the Nose plugin contract.
        """
        return inspect.getdoc(self)


class SelectBucket(Plugin):
    """Select tests from buckets derived from their names.

    Each test's ID is hashed into a number. This number, modulo the given
    number of "buckets", defines the "bucket" for the test. This bucket can
    then be selected by an option. This gives a caller a rough but stable way
    to split up a test suite into parts, for running in parallel perhaps.

    Note that, when using this plug-in, the nose-progressive plug-in will be
    inoperative. Both this and nose-progressive attempt to customise the test
    runner, but this wins.
    """

    name = "select-bucket"
    option_selected_bucket = "%s_selected_bucket" % name
    log = logging.getLogger("nose.plugins.%s" % name)
    score = 10001  # Run before nose-progressive.

    def options(self, parser, env):
        """Add options to Nose's parser.

        :attention: This is part of the Nose plugin contract.
        """
        # This plugin is not compatible with django-nose. Nose passes in an
        # optparse-based argument parser, which django-nose later strips,
        # putting the options into an argparse-based parser. This breaks
        # because argparse uses `type` and `action` instead of `callback` but
        # django-nose does not provide a compatibility shim for that. We could
        # probably work around that here, but django-nose is deprecated in
        # MAAS so it's not worth the effort. Hence, when django_nose has been
        # loaded, this plugin is simply disabled.
        if "django_nose" in sys.modules:
            return

        super().options(parser, env)
        parser.add_option(
            "--%s" % self.name,
            dest=self.option_selected_bucket,
            action="callback",
            callback=self._ingestSelectedBucket,
            type="str",
            metavar="BUCKET/BUCKETS",
            default=None,
            help=(
                "Select the number of buckets in which to split tests, and "
                "which of these buckets to then run, e.g. 8/13 will split "
                "tests into 13 buckets and will run those in the 8th bucket "
                "(well... the 7th; the bucket number is indexed from 1)."
            ),
        )

    def configure(self, options, conf):
        """Configure, based on the parsed options.

        :attention: This is part of the Nose plugin contract.
        """
        super().configure(options, conf)
        if self.enabled:
            bucket_buckets = getattr(options, self.option_selected_bucket)
            if bucket_buckets is None:
                self._selectTest = None
            else:
                bucket, buckets = bucket_buckets
                offset = bucket - 1  # Zero-based bucket number.
                self._selectTest = lambda test: (
                    sum(map(ord, test.id())) % buckets == offset
                )

    def _ingestSelectedBucket(self, option, option_string, value, parser):
        """Callback for the `--select-bucket` option.

        The recognises values that match two integers. The latter is the total
        number of buckets, the first is which of those buckets to select
        (starting at 1).
        """
        try:
            value = self._parseSelectedBucket(value)
        except ValueError as error:
            raise optparse.OptionValueError(f"{option_string}: {error}")  # noqa: B904
        else:
            setattr(parser.values, option.dest, value)

    def _parseSelectedBucket(self, option):
        """Helper for `_ingestSelectedBucket`."""
        if option is None:
            return None
        elif "/" in option:
            bucket, buckets = option.split("/", 1)
            try:
                bucket = int(bucket)
                buckets = int(buckets)
            except ValueError:
                raise ValueError("not bucket/buckets")  # noqa: B904
            else:
                if buckets <= 0:
                    raise ValueError("buckets must be >= 0")
                elif bucket <= 0:
                    raise ValueError("bucket must be >= 0")
                elif bucket > buckets:
                    raise ValueError("bucket must be <= buckets")
                else:
                    return bucket, buckets
        else:
            raise ValueError("not bucket/buckets")

    def prepareTestRunner(self, runner):
        """Convert `runner` to a selective variant.

        :attention: This is part of the Nose plugin contract.
        """
        if self._selectTest is not None:
            return SelectiveTestRunner(runner, self._selectTest)

    def help(self):
        """Used in the --help text.

        :attention: This is part of the Nose plugin contract.
        """
        return inspect.getdoc(self)


class SelectiveTestRunner:
    """Wrap a test runner in order to filter the test suite to run."""

    def __init__(self, runner, select):
        super().__init__()
        self._runner = runner
        self._select = select

    def run(self, test):
        if isinstance(test, unittest.TestSuite):
            tests = flattenTests(test)
            tests = filter(self._select, tests)
            test = type(test)(tests)
        else:
            raise TypeError(
                "Expected test suite, got %s: %r"
                % (type(test).__class__.__name__, test)
            )

        return self._runner.run(test)


class Subunit(Plugin):
    """Emit test results as a subunit stream."""

    name = "subunit"
    option_fd = "%s_fd" % name
    log = logging.getLogger("nose.plugins.%s" % name)
    score = 2000  # Run really early, beating even xunit.

    def options(self, parser, env):
        """Add options to Nose's parser.

        :attention: This is part of the Nose plugin contract.
        """
        super().options(parser, env)
        parser.add_option(
            "--%s-fd" % self.name,
            type=int,
            dest=self.option_fd,
            action="store",
            default=1,
            help=(
                "Emit subunit via a specific numeric file descriptor, "
                "stdout (1) by default."
            ),
            metavar="FD",
        )

    def configure(self, options, conf):
        """Configure, based on the parsed options.

        :attention: This is part of the Nose plugin contract.
        """
        super().configure(options, conf)
        if self.enabled:
            # Process --${name}-fd.
            fd = getattr(options, self.option_fd)
            self.stream = open(fd, "wb")

    def prepareTestResult(self, result):
        from subunit import TestProtocolClient

        return TestProtocolClient(self.stream)

    def help(self):
        """Used in the --help text.

        :attention: This is part of the Nose plugin contract.
        """
        return inspect.getdoc(self)


class CleanTestToolsFailure(Plugin):
    """Clean up the failures and errors from testtools."""

    name = "clean-testtools-failure"
    log = logging.getLogger("nose.plugins.%s" % name)

    def formatFailure(self, test, err):
        ec, ev, tb = err
        if ec is not _StringException:
            return err
        if hasattr(ev, "args"):
            return Exception, Exception(*ev.args), tb
        return Exception, Exception(ev), tb

    formatError = formatFailure

    def help(self):
        """Used in the --help text.

        :attention: This is part of the Nose plugin contract.
        """
        return inspect.getdoc(self)


def main():
    """Invoke Nose's `TestProgram` with extra plugins.

    At the command-line it's still necessary to enable these with the flags
    ``--with-crochet``, ``--with-resources``, ``--with-scenarios``, and so on.
    """
    return TestProgram(
        addplugins=(
            CleanTestToolsFailure(),
            Crochet(),
            Resources(),
            Scenarios(),
            Select(),
            SelectBucket(),
            Subunit(),
        )
    )
