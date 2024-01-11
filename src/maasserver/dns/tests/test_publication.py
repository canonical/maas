# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.dns.publication`."""


from datetime import datetime, timedelta

from pytz import UTC
from twisted.internet.defer import fail, inlineCallbacks
from twisted.internet.task import Clock

from maasserver.dns import publication
from maasserver.models.dnspublication import DNSPublication
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maastesting.crochet import wait_for
from maastesting.factory import factory
from maastesting.runtest import MAASCrochetRunTest
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.twisted import pause


def _is_expected_interval(interval):
    return 3 * 60 * 60 <= interval <= 6 * 60 * 60


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
        deferToDatabase.assert_not_called()
        self.assertTrue(_is_expected_interval(dnsgc._loop.interval))

        clock.advance(dnsgc._loop.interval)
        deferToDatabase.assert_called_once_with(dnsgc._collectGarbage, cutoff)
        self.assertTrue(_is_expected_interval(dnsgc._loop.interval))

        dnsgc.stopService()
        self.assertFalse(dnsgc.running)
        self.assertFalse(dnsgc._loop.running)

    def test_failures_are_logged(self):
        exception = factory.make_exception()
        deferToDatabase = self.patch(publication, "deferToDatabase")
        deferToDatabase.return_value = fail(exception)

        dnsgc = publication.DNSPublicationGarbageService()
        dnsgc.clock = clock = Clock()

        with TwistedLoggerFixture() as logger:
            dnsgc.startService()
            clock.advance(dnsgc._loop.interval)
            dnsgc.stopService()

        self.assertEqual(
            logger.output,
            "Failure when removing old DNS publications.\n"
            "Traceback (most recent call last):\n"
            f"Failure: maastesting.factory.{type(exception).__name__}: \n",
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

        DNSPublication.objects.collect_garbage.assert_called_once_with(cutoff)
