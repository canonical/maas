# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for Twisted code."""

__all__ = [
    "extract_result",
]

from copy import copy

from fixtures import Fixture
from testtools.content import Content, UTF8_TEXT
from testtools.monkey import patch
from testtools.twistedsupport._deferred import extract_result
from twisted.internet import defer
from twisted.logger import formatEvent, globalLogPublisher, LogLevel
from twisted.python import log


class TwistedLoggerFixture(Fixture):
    """Capture all Twisted logging.

    Temporarily replaces all log observers.
    """

    def __init__(self):
        super().__init__()
        self.events = []

    @property
    def messages(self):
        """Return a list of events formatted with `t.logger.formatEvent`.

        This returns a list of *strings*, not event dictionaries.
        """
        return [formatEvent(event) for event in self.events]

    @property
    def errors(self):
        """Return a list of events that are at `LogLevel.error` or above.

        This returns a list of event *dictionaries*, not strings.
        """
        return [
            event
            for event in self.events
            if "log_level" in event
            and event["log_level"] is not None
            and event["log_level"] >= LogLevel.error
        ]

    @property
    def failures(self):
        """Return a list of `Failure` instances from events."""

        def find_failure(event):
            if "failure" in event:
                return event["failure"]
            elif "log_failure" in event:
                return event["log_failure"]
            else:
                return None

        failures = map(find_failure, self.events)
        return [failure for failure in failures if failure is not None]

    def dump(self):
        """Return a string of events formatted with `textFromEventDict`.

        This returns a single string, where each log message is separated from
        the next by a line containing "---". Formatting is done by Twisted's
        *legacy* log machinery, which may or may not differ from the modern
        machinery.
        """
        return "\n---\n".join(
            log.textFromEventDict(event) for event in self.events
        )

    # For compatibility with fixtures.FakeLogger.
    output = property(dump)

    def getContent(self):
        """Return a `Content` instance for this fixture.

        `TwistedLoggerFixture` does not automatically add details to itself
        because more often than not these logs are meant to be tested directly
        and not kept.
        """

        def render(events=self.events):
            for event in events:
                rendered = formatEvent(event)
                if rendered is not None:
                    yield rendered.encode("utf-8")

        return Content(UTF8_TEXT, render)

    def setUp(self):
        super().setUp()
        # First remove all observers via the legacy API.
        for observer in list(log.theLogPublisher.observers):
            self.addCleanup(log.theLogPublisher.addObserver, observer)
            log.theLogPublisher.removeObserver(observer)
        # Now remove any remaining modern observers.
        self.addCleanup(patch(globalLogPublisher, "_observers", []))
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
