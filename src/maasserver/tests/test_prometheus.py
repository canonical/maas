# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver.prometheus."""

__all__ = []

from django.db import transaction
from maasserver import prometheus
from maasserver.models import Config
from maasserver.prometheus import push_stats_to_prometheus
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maastesting.matchers import (
    MockCalledOnce,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result
from provisioningserver.utils.twisted import asynchronous
from twisted.application.internet import TimerService
from twisted.internet.defer import fail


class TestPrometheus(MAASServerTestCase):

    def test_push_stats_to_prometheus(self):
        factory.make_RegionRackController()
        maas_name = 'random.maas'
        push_gateway = '127.0.0.1:2000'
        registry_mock = self.patch(prometheus, "CollectorRegistry")
        self.patch(prometheus, "Gauge")
        mock = self.patch(prometheus, "push_to_gateway")
        push_stats_to_prometheus(maas_name, push_gateway)
        self.assertThat(
            mock, MockCalledOnceWith(
                push_gateway,
                job="stats_for_%s" % maas_name,
                registry=registry_mock()))


class TestPrometheusService(MAASTestCase):
    """Tests for `ImportPrometheusService`."""

    def test__is_a_TimerService(self):
        service = prometheus.PrometheusService()
        self.assertIsInstance(service, TimerService)

    def test__runs_once_an_hour_by_default(self):
        service = prometheus.PrometheusService()
        self.assertEqual(3600, service.step)

    def test__calls__maybe_make_stats_request(self):
        service = prometheus.PrometheusService()
        self.assertEqual(
            (service.maybe_push_prometheus_stats, (), {}),
            service.call)

    def test_maybe_make_stats_request_does_not_error(self):
        service = prometheus.PrometheusService()
        deferToDatabase = self.patch(prometheus, "deferToDatabase")
        exception_type = factory.make_exception_type()
        deferToDatabase.return_value = fail(exception_type())
        d = service.maybe_push_prometheus_stats()
        self.assertIsNone(extract_result(d))


class TestPrometheusServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `PrometheusService`."""

    def test_maybe_make_stats_request_makes_request(self):
        mock_call = self.patch(prometheus, "push_stats_to_prometheus")
        setting = self.patch(prometheus, "PROMETHEUS")
        setting.return_value = True

        with transaction.atomic():
            Config.objects.set_config('prometheus_enabled', True)
            Config.objects.set_config(
                'prometheus_push_gateway', '192.168.1.1:8081')

        service = prometheus.PrometheusService()
        maybe_push_prometheus_stats = asynchronous(
            service.maybe_push_prometheus_stats)
        maybe_push_prometheus_stats().wait(5)

        self.assertThat(mock_call, MockCalledOnce())

    def test_maybe_make_stats_request_doesnt_make_request(self):
        mock_call = self.patch(prometheus, "push_stats_to_prometheus")

        with transaction.atomic():
            Config.objects.set_config('enable_analytics', False)

        service = prometheus.PrometheusService()
        maybe_push_prometheus_stats = asynchronous(
            service.maybe_push_prometheus_stats)
        maybe_push_prometheus_stats().wait(5)

        self.assertThat(mock_call, MockNotCalled())
