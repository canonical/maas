# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for Twisted code."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "always_fail_with",
    "always_succeed_with",
    "TwistedLoggerFixture",
]

from copy import copy
import operator

from fixtures import Fixture
from twisted.internet import defer
from twisted.python import log


class TwistedLoggerFixture(Fixture):
    """Capture all Twisted logging.

    Temporarily replaces all log observers.
    """

    def __init__(self):
        super(TwistedLoggerFixture, self).__init__()
        self.logs = []
        # Check if new logger from Twisted 15+ is being used.
        self.isNewLogger = hasattr(log.theLogPublisher, "_publishPublisher")

    def dump(self):
        """Return all logs as a string."""
        return "\n---\n".join(
            log.textFromEventDict(event) for event in self.logs)

    # For compatibility with fixtures.FakeLogger.
    output = property(dump)

    def containsError(self):
        return any(log["isError"] for log in self.logs)

    def newSetUp(self):
        """Twisted 15+ uses a new logger."""
        self._publishPublisher = log.theLogPublisher._publishPublisher
        log.theLogPublisher._publishPublisher = self.logs.append

    def newCleanUp(self):
        """Twisted 15+ uses a new logger."""
        log.theLogPublisher._publishPublisher = self._publishPublisher

    def setUp(self):
        super(TwistedLoggerFixture, self).setUp()
        if self.isNewLogger:
            self.addCleanup(self.newCleanUp)
            self.newSetUp()
        else:
            self.addCleanup(
                operator.setitem, log.theLogPublisher.observers,
                slice(None), log.theLogPublisher.observers[:])
            log.theLogPublisher.observers[:] = [self.logs.append]


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
