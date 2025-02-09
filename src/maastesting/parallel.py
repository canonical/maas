# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Run MAAS's tests in parallel."""

import abc
import argparse
import copy
import os
import queue
import re
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest

import junitxml
import subunit
import testtools

from maastesting.utils import content_from_file


class TestScriptBase(metaclass=abc.ABCMeta):
    """A test-like object that wraps one of the `bin/test.*` scripts."""

    def __init__(self, lock, script, with_subunit=True, has_script=True):
        super().__init__()
        self.lock = lock
        assert isinstance(script, str)
        self.script = script
        self.with_subunit = with_subunit
        self.has_script = has_script

    @abc.abstractmethod
    def id(self):
        """Return an ID for this test, as a string."""

    @abc.abstractmethod
    def split(self, parts):
        """Split this test up into `parts` parts, or not.

        The implementation is free to choose, but it should return an iterable
        of between 1 and `parts` tests.
        """

    @abc.abstractmethod
    def select(self, selectors):
        """Return a new script, narrowed to the given selectors.

        If none of the selectors are relevant to this script, return `None`.
        """

    def extendCommand(self, command):
        """Provide a hook to extending a command (a tuple) with additional arguments.

        Subclasses can extend it.
        """
        return command

    def run(self, result):
        with tempfile.NamedTemporaryFile(prefix="maas-parallel-test") as log:
            try:
                okay = self._run(result, log)
            except Exception:
                result.addError(
                    self,
                    None,
                    {
                        "log": content_from_file(log.name),
                        "traceback": testtools.content.TracebackContent(
                            sys.exc_info(), self, capture_locals=False
                        ),
                    },
                )
            else:
                if not okay:
                    result.addError(
                        self, None, {"log": content_from_file(log.name)}
                    )

    def _run(self, result, log):
        # Build things first, which may do nothing (but is quick).
        with self.lock:
            subprocess.check_call(
                ("make", "--quiet", self.script),
                stdout=log,
                stderr=log,
            )

        if not self.has_script:
            # If there is no script to run, then everything is OK.
            return True
        # Run the script in a subprocess, capturing subunit output if
        # with_subunit is set.
        pread, pwrite = os.pipe()
        with open(pread, "rb") as preader:
            try:
                args = [self.script]
                if self.with_subunit:
                    args.extend(("--with-subunit", "--subunit-fd=%d" % pwrite))
                command = self.extendCommand(args)
                process = subprocess.Popen(
                    command, pass_fds={pwrite}, stdout=log, stderr=log
                )
            finally:
                os.close(pwrite)

            server = subunit.TestProtocolServer(result, sys.stdout.buffer)
            # Don't use TestProtocolServer.readFrom because it blocks until
            # the stream is complete (it uses readlines).
            for line in preader:
                server.lineReceived(line)
            server.lostConnection()

            return process.wait() == 0

    __call__ = run

    def __repr__(self, details=()):
        details = " ".join((self.script, *details))
        return f"<{self.__class__.__name__} {details}>"


class TestScriptDivisible(TestScriptBase):
    """A variant of `TestScriptBase` that can be split."""

    _bucket = 1, 1

    def id(self):
        return "{}#{}/{}".format(self.script, *self._bucket)

    def split(self, buckets):
        for bucket in range(buckets):
            new = copy.copy(self)
            new._bucket = (bucket + 1), buckets
            yield new

    def extendCommand(self, command):
        return super().extendCommand(
            (
                *command,
                "--with-select-bucket",
                "--select-bucket",
                "%d/%d" % self._bucket,
            )
        )

    def __repr__(self, details=()):
        details = (*details, "bucket=%d/%d" % self._bucket)
        return super().__repr__(details)


class TestScriptIndivisible(TestScriptBase):
    """A variant of `TestScriptBase` that cannot be split."""

    def id(self):
        return self.script

    def split(self, buckets):
        yield self


class TestScriptSelectable(TestScriptBase):
    """A variant of `TestScriptBase` that can be matched / selected."""

    def __init__(self, lock, script, *patterns):
        super().__init__(lock, script)
        self.patterns = patterns
        self.selectors = ()

    def select(self, selectors):
        """Compare `selectors` against this test's patterns.

        If they match, return a copy of self narrowed down according to those
        selectors, otherwise return `None`. If there are no selectors, return
        self unmodified.
        """
        if len(selectors) == 0:
            return self
        else:
            pattern = re.compile("(?:%s)" % "|".join(self.patterns))
            matched = tuple(
                selector
                for selector in selectors
                if pattern.match(selector) is not None
            )
            if len(matched) == 0:
                return None
            else:
                self = copy.copy(self)
                self.selectors = matched
                return self

    def extendCommand(self, command):
        return super().extendCommand((*command, "--", *self.selectors))

    def __repr__(self, details=()):
        if len(self.selectors) != 0:
            details = (*details, "--", *self.selectors)
        return super().__repr__(details)


class TestScriptUnselectable(TestScriptBase):
    """A variant of `TestScriptBase` that cannot be matched / selected."""

    def select(self, selectors):
        """This script is only selected when there are no selectors."""
        if len(selectors) == 0:
            return self
        else:
            self._warnAboutSelectors()
            return None

    def _warnAboutSelectors(self):
        """Print out a warning about using selectors with this script."""
        warning = textwrap.dedent(
            """\
            WARNING: {script.script} will _never_ be selected when using
            selectors at the command-line. Run {script.script} directly.
        """.format(script=self)
        )
        for line in textwrap.wrap(warning, 72):
            print(line, file=sys.stderr)


class TestScript(TestScriptDivisible, TestScriptSelectable):
    """A test script that can be split and can make use of selectors."""


class TestScriptMonolithic(TestScriptIndivisible, TestScriptUnselectable):
    """A test script that cannot be split and does not grok selectors."""


class TestProcessor:
    """A `TestSuite`-like object that runs tests pulled from a queue.

    A batch of these are given to `ConcurrentTestSuite` by the "splitter"
    function (which testtools calls `make_tests`).
    """

    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def run(self, result):
        for test in iter(self.queue.get, None):
            if result.shouldStop:
                break
            else:
                test(result)


def make_splitter(splits):
    """Make a function that will split `TestScriptBase` instances.

    :param splits: The number of parts in which to split tests.
    """
    backlog = queue.Queue()
    procs = tuple(TestProcessor(backlog) for _ in range(splits))

    def split(test):
        for script in testtools.iterate_tests(test):
            for script in script.split(splits):  # noqa: B020
                backlog.put(script)
        for _ in procs:
            backlog.put(None)
        return procs

    return split


def make_human_readable_result(stream):
    """Make a result that emits messages intended for human consumption."""

    def print_result(test, status, start_time, stop_time, tags, details):
        testid = "<none>" if test is None else test.id()
        duration = (stop_time - start_time).total_seconds()
        message = f"{status.upper()}: {testid} ({abs(duration):0.2f}s)"
        print(message, file=stream, flush=True)

    return testtools.MultiTestResult(
        testtools.TextTestResult(stream, failfast=False, tb_locals=False),
        testtools.TestByTestResult(print_result),
    )


def make_subunit_result(stream):
    """Make a result that emits a subunit stream."""
    return subunit.TestProtocolClient(stream)


def make_junit_result(stream):
    """Make a result that emits JUnit-compatible XML results."""
    return junitxml.JUnitXmlResult(stream)


def test(suite, result, processes):
    """Test `suite`, emitting results to `result`.

    :param suite: The test suite to run.
    :param result: The test result to which to report.
    :param processes: The number of processes to split up tests amongst.
    :return: A boolean signalling success or not.
    """
    split = make_splitter(processes)
    suite = testtools.ConcurrentTestSuite(suite, split)

    result.startTestRun()
    try:
        suite.run(result)
    finally:
        result.stopTestRun()

    return result.wasSuccessful()


def make_argument_parser(scripts):
    """Create an argument parser for the command-line."""
    description = (
        __doc__
        + " "
        + (
            "This delegates the actual work to several test programs: %s."
            % ", ".join(script.script for script in scripts)
        )
    )
    parser = argparse.ArgumentParser(description=description, add_help=False)
    parser.add_argument("-h", "--help", action="help", help=argparse.SUPPRESS)
    core_count = os.cpu_count()

    def parse_subprocesses(string):
        try:
            processes = int(string)
        except ValueError:
            raise argparse.ArgumentTypeError("%r is not an integer" % string)  # noqa: B904
        else:
            if processes < 1:
                raise argparse.ArgumentTypeError(
                    "%d is not 1 or greater" % processes
                )
            else:
                return processes

    args_subprocesses = parser.add_mutually_exclusive_group()
    args_subprocesses.add_argument(
        "--subprocesses",
        metavar="N",
        action="store",
        type=parse_subprocesses,
        dest="subprocesses",
        default=max(2, core_count - 2),
        help=(
            "The number of testing subprocesses to run concurrently. This "
            "defaults to the number of CPU cores available minus 2, but not "
            "less than 2. On this machine the default is %(default)s."
        ),
    )
    args_subprocesses.add_argument(
        "--subprocess-per-core",
        action="store_const",
        dest="subprocesses",
        const=core_count,
        help=(
            "Run one test process per core. On this machine that would mean "
            "that up to %d testing subprocesses would run concurrently."
            % core_count
        ),
    )

    args_output = parser.add_argument_group("output")
    args_output.add_argument(
        "--emit-human",
        dest="result_factory",
        action="store_const",
        const=make_human_readable_result,
        help="Emit human-readable results.",
    )
    args_output.add_argument(
        "--emit-subunit",
        dest="result_factory",
        action="store_const",
        const=make_subunit_result,
        help="Emit a subunit stream.",
    )
    args_output.add_argument(
        "--emit-junit",
        dest="result_factory",
        action="store_const",
        const=make_junit_result,
        help="Emit JUnit-compatible XML.",
    )
    args_output.set_defaults(result_factory=make_human_readable_result)

    unselectable = (
        script.script
        for script in scripts
        if isinstance(script, TestScriptUnselectable)
    )
    parser.add_argument(
        "selectors",
        nargs="*",
        metavar="SELECTOR",
        help="Selectors to narrow "
        "the tests to run. Note that when selectors are used, unselectable "
        "scripts (%s) will *never* be selected." % ", ".join(unselectable),
    )

    return parser


def main(args=None):
    lock = threading.Lock()
    scripts = (
        # Run the monolithic tests first. These will each consume a worker
        # thread (spawned by ConcurrentTestSuite) for a prolonged duration.
        # Putting divisible tests afterwards evens out the spread of work.
        TestScriptMonolithic(lock, "bin/test.region.legacy"),
        # The divisible test scripts will each be executed multiple times,
        # each time to work on a distinct "bucket" of tests.
        TestScript(
            lock,
            "bin/test.rack",
            r"^src/provisioningserver\b",
            r"^provisioningserver\b",
        ),
        TestScript(
            lock,
            "bin/test.region",
            r"^src/(maas|metadata)server\b",
            r"^(maas|metadata)server\b",
        ),
    )
    # Parse arguments.
    args = make_argument_parser(scripts).parse_args(args)
    # Narrow scripts down to the given selectors.
    scripts = (script.select(args.selectors) for script in scripts)
    scripts = [script for script in scripts if script is not None]
    suite = unittest.TestSuite(scripts)
    result = args.result_factory(sys.stdout)
    if test(suite, result, args.subprocesses):
        raise SystemExit(0)
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
