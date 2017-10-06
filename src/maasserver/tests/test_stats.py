# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver.stats."""

__all__ = []

from django.db import transaction
from maasserver import stats
from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maastesting.matchers import (
    MockCalledOnce,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result
from provisioningserver.utils.twisted import asynchronous
from twisted.application.internet import TimerService
from twisted.internet.defer import fail


class TestStatsService(MAASTestCase):
    """Tests for `ImportStatsService`."""

    def test__is_a_TimerService(self):
        service = stats.StatsService()
        self.assertIsInstance(service, TimerService)

    def test__runs_once_a_day(self):
        service = stats.StatsService()
        self.assertEqual(86400, service.step)

    def test__calls__maybe_make_stats_request(self):
        service = stats.StatsService()
        self.assertEqual(
            (service.maybe_make_stats_request, (), {}),
            service.call)

    def test_maybe_make_stats_request_does_not_error(self):
        service = stats.StatsService()
        deferToDatabase = self.patch(stats, "deferToDatabase")
        exception_type = factory.make_exception_type()
        deferToDatabase.return_value = fail(exception_type())
        d = service.maybe_make_stats_request()
        self.assertIsNone(extract_result(d))


class TestStatsServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `StatsService`."""

    def test_maybe_make_stats_request_makes_request(self):
        mock_call = self.patch(stats, "make_maas_user_agent_request")

        with transaction.atomic():
            Config.objects.set_config('enable_analytics', True)

        service = stats.StatsService()
        maybe_make_stats_request = asynchronous(
            service.maybe_make_stats_request)
        maybe_make_stats_request().wait(5)

        self.assertThat(mock_call, MockCalledOnce())

    def test_maybe_make_stats_request_doesnt_make_request(self):
        mock_call = self.patch(stats, "make_maas_user_agent_request")

        with transaction.atomic():
            Config.objects.set_config('enable_analytics', False)

        service = stats.StatsService()
        maybe_make_stats_request = asynchronous(
            service.maybe_make_stats_request)
        maybe_make_stats_request().wait(5)

        self.assertThat(mock_call, MockNotCalled())
