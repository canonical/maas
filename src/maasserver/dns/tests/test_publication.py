# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.dns.publication`."""


from datetime import datetime, timedelta

from pytz import UTC
from testtools.matchers import LessThan, MatchesAll
from twisted.internet.defer import fail, inlineCallbacks
from twisted.internet.task import Clock

from maasserver.dns import publication
from maasserver.models.dnspublication import DNSPublication
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maastesting.crochet import wait_for
from maastesting.factory import factory
from maastesting.matchers import (
    DocTestMatches,
    GreaterThanOrEqual,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.runtest import MAASCrochetRunTest
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.twisted import pause

IsExpectedInterval = MatchesAll(
    GreaterThanOrEqual(3 * 60 * 60), LessThan(6 * 60 * 60), first_only=True
)


def patch_utcnow(test):
    utcnow = test.patch(publication, "datetime").utcnow
    ref = utcnow.return_value = datetime.utcnow()
    return ref


class TestDNSPublicationGarbageService(MAASTestCase):
    """Tests for `DNSPublicationGarbageService`."""

    run_tests_with = MAASCrochetRunTest

    def test_starting_and_stopping(self):
        deferToDatabase = self.patch(publication, "deferToDatabase")

        utcnow = patch_utcnow(self)
        cutoff = utcnow.replace(tzinfo=UTC) - timedelta(days=7)

        dnsgc = publication.DNSPublicationGarbageService()
        dnsgc.clock = clock = Clock()

        dnsgc.startService()
        self.assertTrue(dnsgc.running)
        self.assertTrue(dnsgc._loop.running)
        self.assertThat(deferToDatabase, MockNotCalled())
        self.assertThat(dnsgc._loop.interval, IsExpectedInterval)

        clock.advance(dnsgc._loop.interval)
        self.assertThat(
            deferToDatabase, MockCalledOnceWith(dnsgc._collectGarbage, cutoff)
        )
        self.assertThat(dnsgc._loop.interval, IsExpectedInterval)

        dnsgc.stopService()
        self.assertFalse(dnsgc.running)
        self.assertFalse(dnsgc._loop.running)

    def test_failures_are_logged(self):
        deferToDatabase = self.patch(publication, "deferToDatabase")
        deferToDatabase.return_value = fail(factory.make_exception())

        dnsgc = publication.DNSPublicationGarbageService()
        dnsgc.clock = clock = Clock()

        with TwistedLoggerFixture() as logger:
            dnsgc.startService()
            clock.advance(dnsgc._loop.interval)
            dnsgc.stopService()

        self.assertThat(
            logger.output,
            DocTestMatches(
                """\
            Failure when removing old DNS publications.
            Traceback (most recent call last):...
            Failure: maastesting.factory.TestException#...
            """
            ),
        )

        self.assertFalse(dnsgc.running)


class TestDNSPublicationGarbageServiceWithDatabase(
    MAASTransactionServerTestCase
):
    """Tests for `DNSPublicationGarbageService` with the database."""

    run_tests_with = MAASCrochetRunTest

    @wait_for()
    @inlineCallbacks
    def test_garbage_is_collected(self):
        dnsgc = publication.DNSPublicationGarbageService()

        utcnow = patch_utcnow(self)
        cutoff = utcnow.replace(tzinfo=UTC) - timedelta(days=7)

        self.patch(dnsgc, "_getInterval").side_effect = [0, 999]
        self.patch(DNSPublication.objects, "collect_garbage")

        yield dnsgc.startService()
        yield pause(0.0)  # Let the reactor tick.
        yield dnsgc.stopService()

        self.assertThat(
            DNSPublication.objects.collect_garbage, MockCalledOnceWith(cutoff)
        )
