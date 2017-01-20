# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Run MAAS's tests in parallel."""

import abc
import argparse
import copy
import io
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest

from maastesting.utils import content_from_file
import subunit
import testtools


class TestScript(metaclass=abc.ABCMeta):
    """A test-like object that wraps one of the `bin/test.*` scripts."""

    def __init__(self, lock, script):
        super(TestScript, self).__init__()
        self.lock = lock
        assert isinstance(script, str)
        self.script = script

    @abc.abstractmethod
    def id(self):
        """Return an ID for this test, as a string."""

    @abc.abstractmethod
    def split(self, parts):
        """Split this test up into `parts` parts, or not.

        The implementation is free to choose, but it should return an iterable
        of between 1 and `parts` tests.
        """

    def extendCommand(self, command):
        """Extend the command (a tuple) with additional arguments."""
        return command

    def run(self, result):
        with tempfile.NamedTemporaryFile() as log:
            try:
                okay = self._run(result, log)
            except:
                result.addError(self, None, {
                    "log": content_from_file(log.name),
                    "traceback": testtools.content.TracebackContent(
                        sys.exc_info(), self, capture_locals=False),
                })
            else:
                if not okay:
                    result.addError(self, None, {
                        "log": content_from_file(log.name),
                    })

    def _run(self, result, log):
        # Build the script first, which may do nothing (but is quick).
        with self.lock:
            subprocess.check_call(
                ("make", "--quiet", self.script), stdout=log, stderr=log)
        # Run the script in a subprocess, capturing subunit output.
        pread, pwrite = os.pipe()
        with io.open(pread, "rb") as preader:
            try:
                command = self.extendCommand((
                    self.script, "--with-subunit", "--subunit-fd=%d" % pwrite))
                process = subprocess.Popen(
                    command, pass_fds={pwrite}, stdout=log, stderr=log)
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

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.script)


class TestScriptDivisible(TestScript):
    """A variant of `TestScript` that can be split."""

    _bucket = 1, 1

    def id(self):
        return "{}#{}/{}".format(self.script, *self._bucket)

    def split(self, buckets):
        for bucket in range(buckets):
            new = copy.copy(self)
            new._bucket = (bucket + 1), buckets
            yield new

    def extendCommand(self, command):
        return command + (
            "--with-select-bucket",
            "--select-bucket", "%d/%d" % self._bucket,
        )

    def __repr__(self):
        bucket, buckets = self._bucket
        return "<%s %s bucket=%d/%d>" % (
            self.__class__.__name__, self.script, bucket, buckets)


class TestScriptIndivisible(TestScript):
    """A variant of `TestScript` that cannot be split."""

    def id(self):
        return self.script

    def split(self, buckets):
        yield self


class TestProcessor:
    """A `TestSuite`-like object that runs tests pulled from a queue.

    A batch of these are given to `ConcurrentTestSuite` by the "splitter"
    function (which testtools calls `make_tests`).
    """

    def __init__(self, queue):
        super(TestProcessor, self).__init__()
        self.queue = queue

    def run(self, result):
        for test in iter(self.queue.get, None):
            if result.shouldStop:
                break
            else:
                test(result)


def make_splitter(splits):
    """Make a function that will split `TestScript` instances.

    :param splits: The number of parts in which to split tests.
    """
    backlog = queue.Queue()
    procs = tuple(TestProcessor(backlog) for _ in range(splits))

    def split(test):
        for script in testtools.iterate_tests(test):
            for script in script.split(splits):
                backlog.put(script)
        for _ in procs:
            backlog.put(None)
        return procs

    return split


def print_test(test, status, start_time, stop_time, tags, details):
    testid = "<none>" if test is None else test.id()
    duration = (stop_time - start_time).total_seconds()
    message = "%s: %s (%0.2fs)" % (status.upper(), testid, abs(duration))
    print(message, flush=True)


def test(suite):
    parts = max(2, os.cpu_count() - 2)
    split = make_splitter(parts)
    suite = testtools.ConcurrentTestSuite(suite, split)
    result = testtools.MultiTestResult(
        testtools.TestByTestResult(print_test),
        testtools.TextTestResult(
            sys.stdout, failfast=False, tb_locals=False),
    )

    result.startTestRun()
    try:
        suite.run(result)
    finally:
        result.stopTestRun()

    raise SystemExit(0 if result.wasSuccessful() else 2)


argument_parser = argparse.ArgumentParser(description=__doc__)


def main():
    args = argument_parser.parse_args()  # noqa
    lock = threading.Lock()
    suite = unittest.TestSuite((
        # Run the indivisible tests first. These will each consume a worker
        # thread (spawned by ConcurrentTestSuite) for a prolonged duration.
        # Putting divisible tests afterwards evens out the spread of work.
        TestScriptIndivisible(lock, "bin/test.js"),
        TestScriptIndivisible(lock, "bin/test.region.legacy"),
        # The divisible test scripts will each be executed multiple times,
        # each time to work on a distinct "bucket" of tests.
        TestScriptDivisible(lock, "bin/test.cli"),
        TestScriptDivisible(lock, "bin/test.rack"),
        TestScriptDivisible(lock, "bin/test.region"),
        TestScriptDivisible(lock, "bin/test.testing"),
    ))
    test(suite)


if __name__ == '__main__':
    main()
