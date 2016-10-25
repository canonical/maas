# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Twisted-specific logging stuff."""

__all__ = []

from functools import partial
import io
from unittest.mock import (
    patch,
    sentinel,
)

from maastesting.factory import factory
from maastesting.matchers import DocTestMatches
from maastesting.testcase import MAASTestCase
from provisioningserver.logger._twisted import LegacyLogObserverWrapper
from testtools.matchers import (
    AllMatch,
    Contains,
    ContainsAll,
    ContainsDict,
    Equals,
    HasLength,
    Is,
    IsInstance,
    MatchesAll,
    MatchesSetwise,
    Not,
)
from twisted import logger
from twisted.python import log


def ContainsDictByEquality(expected):
    return ContainsDict(
        {key: Equals(value) for key, value in expected.items()})


def setLegacyObservers(observers):
    """Remove existing legacy log observers, add those given."""
    for observer in log.theLogPublisher.observers:
        log.theLogPublisher.removeObserver(observer)
    for observer in observers:
        log.theLogPublisher.addObserver(observer)


class TestLegacyLogObserverWrapper(MAASTestCase):
    """Scenario tests for `LegacyLogObserverWrapper`."""

    scenarios = tuple(
        (log_level.name, dict(log_level=log_level))
        for log_level in logger.LogLevel.iterconstants()
    )

    def processEvent(self, event):
        events = []
        observer = LegacyLogObserverWrapper(events.append)
        observer(event)
        self.assertThat(events, HasLength(1))
        return events[0]

    def test__adds_log_system_and_system_to_event(self):
        self.assertThat(
            # This is a `twisted.logger` event, not legacy, and requires
            # values for `log_time` and `log_level` at a minimum.
            self.processEvent({
                "log_time": sentinel.log_time,
                "log_level": self.log_level,
            }),
            ContainsDictByEquality({
                "log_system": "-#" + self.log_level.name,
                "system": "-#" + self.log_level.name,
            }),
        )

    def test__adds_log_system_and_system_to_event_with_namespace(self):
        log_namespace = factory.make_name("log_namespace")
        self.assertThat(
            self.processEvent({
                "log_time": sentinel.log_time,
                "log_level": self.log_level,
                "log_namespace": log_namespace,
            }),
            ContainsDictByEquality({
                "log_system": log_namespace + "#" + self.log_level.name,
                "system": log_namespace + "#" + self.log_level.name,
            }),
        )

    def test__adds_log_system_and_system_to_legacy_event(self):
        self.assertThat(
            # This is a `twisted.python.log` event, i.e. legacy, and requires
            # values for `time` and `isError` at a minimum.
            self.processEvent({
                "time": sentinel.time,
                "isError": factory.pick_bool(),
            }),
            ContainsDictByEquality({
                "log_system": "-#-",
                "system": "-#-",
            }),
        )

    def test__preserves_log_system_in_event(self):
        log_system = factory.make_name("log_system")
        self.assertThat(
            self.processEvent({
                "log_time": sentinel.time,
                "log_level": self.log_level,
                "log_system": log_system,
            }),
            # `log_system` is not modified; `system` is set to match.
            ContainsDictByEquality({
                "log_system": log_system,
                "system": log_system,
            }),
        )

    def test__preserves_system_in_legacy_event(self):
        system = factory.make_name("system")
        self.assertThat(
            self.processEvent({
                "time": sentinel.time,
                "isError": factory.pick_bool(),
                "system": system,
            }),
            MatchesAll(
                # `log_system` is not added when `system` already exists.
                Not(Contains("log_system")),
                ContainsDictByEquality({
                    "system": system,
                }),
            ),
        )

    def test__namespace_and_level_is_printed_in_legacy_log(self):
        # Restore existing observers at the end. This must be careful with
        # ordering of clean-ups, hence the use of unittest.mock.patch.object
        # as a context manager.
        self.addCleanup(setLegacyObservers, log.theLogPublisher.observers)
        # The global non-legacy `LogBeginner` emits critical messages straight
        # to stderr, so temporarily put aside its observer to avoid seeing the
        # critical log messages we're going to generate.
        self.patch(logger.globalLogPublisher, "_observers", [])

        logbuffer = io.StringIO()
        observer = log.FileLogObserver(logbuffer)
        observer.formatTime = lambda when: "<timestamp>"

        oldlog = log.msg
        # Deliberately use the default global observer in the new logger
        # because we want to see how it behaves in a typical environment where
        # logs are being emitted by the legacy logging infrastructure, for
        # example running under `twistd`.
        newlog = partial(logger.Logger().emit, self.log_level)

        with patch.object(
                log, "LegacyLogObserverWrapper",
                log.LegacyLogObserverWrapper):
            setLegacyObservers([observer.emit])
            oldlog("Before (legacy)")
            newlog("Before (new)")
            LegacyLogObserverWrapper.install()
            oldlog("After (legacy)")
            newlog("After (new)")

        self.assertThat(
            logbuffer.getvalue(), DocTestMatches("""\
            <timestamp> [-] Before (legacy)
            <timestamp> [-] Before (new)
            <timestamp> [-] After (legacy)
            <timestamp> [%s#%s] After (new)
            """ % (__name__, self.log_level.name)))


class TestLegacyLogObserverWrapper_Installation(MAASTestCase):
    """Tests for `LegacyLogObserverWrapper`."""

    def setUp(self):
        super().setUp()
        # Restore existing observers at the end. Tests must be careful with
        # ordering of clean-ups, hence the use of unittest.mock.patch.object
        # as a context manager in the tests themselves.
        self.addCleanup(setLegacyObservers, log.theLogPublisher.observers)

    def test__installs_wrapper_to_log_module(self):
        with patch.object(log, "LegacyLogObserverWrapper", sentinel.unchanged):
            self.assertThat(
                log.LegacyLogObserverWrapper,
                Is(sentinel.unchanged))
            LegacyLogObserverWrapper.install()
            self.assertThat(
                log.LegacyLogObserverWrapper,
                Is(LegacyLogObserverWrapper))

    def test__rewraps_existing_observers(self):

        class OldWrapper:

            def __init__(self, observer):
                self.legacyObserver = observer

            def __call__(self, event):
                return self.legacyObserver(event)

        with patch.object(log, "LegacyLogObserverWrapper", OldWrapper):

            observers = (lambda event: event), (lambda event: event)
            setLegacyObservers(observers)

            # Our legacy observers are all registered.
            self.assertThat(
                log.theLogPublisher.observers,
                MatchesSetwise(*map(Is, observers)))
            # Behind the scenes they're all wrapped with OldWrapper.
            self.assertThat(
                log.theLogPublisher._legacyObservers,
                AllMatch(IsInstance(OldWrapper)))
            # They're registered with the new global log publisher too.
            self.assertThat(
                logger.globalLogPublisher._observers,
                ContainsAll(log.theLogPublisher._legacyObservers))

            # Install!
            LegacyLogObserverWrapper.install()

            # Our legacy observers are all still registered.
            self.assertThat(
                log.theLogPublisher.observers,
                MatchesSetwise(*map(Is, observers)))
            # Behind the scenes they're now all wrapped with our wrapper.
            self.assertThat(
                log.theLogPublisher._legacyObservers,
                AllMatch(IsInstance(LegacyLogObserverWrapper)))
            # They're registered with the new global log publisher too.
            self.assertThat(
                logger.globalLogPublisher._observers,
                ContainsAll(log.theLogPublisher._legacyObservers))
