# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for TFTP-specific logging stuff."""


from testtools.matchers import Contains, Is
from twisted.logger import LogLevel

from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.logger._tftp import observe_tftp
from provisioningserver.logger.testing import make_event


class TestObserveTwistedInternetTCP_Informational(MAASTestCase):
    """Tests for `observe_tftp` with informational messages."""

    def test_downgrades_informational_messages(self):
        event = make_event(log_level=LogLevel.info)
        with TwistedLoggerFixture() as logger:
            observe_tftp(event)
        self.assertThat(logger.events, Contains(event))
        self.assertThat(event["log_level"], Is(LogLevel.debug))


class TestObserveTwistedInternetTCP_Other(MAASTestCase):
    """Tests for `observe_tftp` with non-informational messages."""

    scenarios = tuple(
        (log_level.name, {"log_level": log_level})
        for log_level in LogLevel.iterconstants()
        if log_level is not LogLevel.info
    )

    def test_propagates_other_events(self):
        event = make_event(log_level=self.log_level)
        with TwistedLoggerFixture() as logger:
            observe_tftp(event)
        self.assertThat(logger.events, Contains(event))
        self.assertThat(event["log_level"], Is(self.log_level))
