# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for Twisted code."""

__all__ = [
    "always_fail_with",
    "always_succeed_with",
    "extract_result",
    "TwistedLoggerFixture",
]

from copy import copy
import inspect
from textwrap import dedent

from fixtures import Fixture
from testtools.deferredruntest import CaptureTwistedLogs
from testtools.twistedsupport._deferred import extract_result
from twisted.internet import defer
from twisted.logger import LogLevel
from twisted.python import log


def maybe_fix_bug_230_in_CaptureTwistedLogs():
    """Fix a bug in testtools's `CaptureTwistedLogs`.

    Specifically "TypeError: CaptureTwistedLogs puts strings into details",
    https://github.com/testing-cabal/testtools/issues/230. At the time of
    writing this has been fixed upstream but not released.
    """
    source = inspect.getsource(CaptureTwistedLogs._setUp)
    if '[logs.getvalue()]' in source:
        source = source.replace("getvalue()", "getvalue().encode('utf-8')")
        namespace = CaptureTwistedLogs._setUp.__globals__.copy()
        exec(dedent(source), namespace)
        CaptureTwistedLogs._setUp = namespace["_setUp"]


class TwistedLoggerFixture(Fixture):
    """Capture all Twisted logging.

    Temporarily replaces all log observers.
    """

    def __init__(self):
        super(TwistedLoggerFixture, self).__init__()
        self.events = []

    def dump(self):
        """Return all logs as a string."""
        return "\n---\n".join(
            log.textFromEventDict(event) for event in self.events)

    # For compatibility with fixtures.FakeLogger.
    output = property(dump)

    @property
    def errors(self):
        """Return events that are at `LogLevel.error` or above."""
        return [
            event for event in self.events
            if "log_level" in event and
            event["log_level"] is not None and
            event["log_level"] >= LogLevel.error
        ]

    def containsError(self):
        return any(event["isError"] for event in self.events)

    def setUp(self):
        super(TwistedLoggerFixture, self).setUp()
        # First remove all observers via the legacy API.
        for observer in list(log.theLogPublisher.observers):
            self.addCleanup(log.theLogPublisher.addObserver, observer)
            log.theLogPublisher.removeObserver(observer)
        # Now add our observer, again via the legacy API. This ensures that
        # it's wrapped with whatever legacy wrapper we've installed.
        self.addCleanup(log.theLogPublisher.removeObserver, self.events.append)
        log.theLogPublisher.addObserver(self.events.append)


def always_succeed_with(result):
    """Return a callable that always returns a successful Deferred.

    The callable allows (and ignores) all arguments, and returns a shallow
    `copy` of `result`.
    """
    def always_succeed(*args, **kwargs):
        return defer.succeed(copy(result))
    return always_succeed


def always_fail_with(result):
    """Return a callable that always returns a failed Deferred.

    The callable allows (and ignores) all arguments, and returns a shallow
    `copy` of `result`.
    """
    def always_fail(*args, **kwargs):
        return defer.fail(copy(result))
    return always_fail
