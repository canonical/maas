# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver.prometheus.stats."""

__all__ = []

import http.client
import json
from unittest import mock

from django.db import transaction
from maasserver.models import Config
from maasserver.prometheus import stats
from maasserver.prometheus.stats import (
    push_stats_to_prometheus,
    STATS_DEFINITIONS,
    update_prometheus_stats,
)
from maasserver.prometheus.utils import create_metrics
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.django_urls import reverse
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


class TestPrometheusHandler(MAASServerTestCase):

    def test_prometheus_stats_handler_returns_http_not_found(self):
        Config.objects.set_config('prometheus_enabled', False)
        response = self.client.get(reverse('stats'))
        self.assertEqual("text/html; charset=utf-8", response["Content-Type"])
        self.assertEquals(response.status_code, http.client.NOT_FOUND)

    def test_prometheus_stats_handler_returns_success(self):
        Config.objects.set_config('prometheus_enabled', True)
        mock_prom_cli = self.patch(stats, 'prom_cli')
        mock_prom_cli.generate_latest.return_value = {}
        response = self.client.get(reverse('stats'))
        self.assertEqual("text/plain", response["Content-Type"])
        self.assertEquals(response.status_code, http.client.OK)

    def test_prometheus_stats_handler_returns_metrics(self):
        Config.objects.set_config('prometheus_enabled', True)
        response = self.client.get(reverse('stats'))
        content = response.content.decode("utf-8")
        metrics = ('nodes', 'machine_resources', 'kvm_pods', 'machine_arches')
        for metric in metrics:
            self.assertIn('TYPE {} gauge'.format(metric), content)


class TestPrometheus(MAASServerTestCase):

    def test_update_prometheus_stats(self):
        self.patch(stats, 'prom_cli')
        # general values
        values = {
            "machine_status": {
                "random_status": 0,
            },
            "controllers": {
                "regions": 0,
            },
            "nodes": {
                "machines": 0,
            },
            "network_stats": {
                "spaces": 0,
            },
            "machine_stats": {
                "total_cpus": 0,
            },
        }
        mock = self.patch(stats, "get_maas_stats")
        mock.return_value = json.dumps(values)
        # architecture
        arches = {
            "amd64": 0,
            "i386": 0,
        }
        mock_arches = self.patch(stats, "get_machines_by_architecture")
        mock_arches.return_value = arches
        # pods
        pods = {
            "kvm_pods": 0,
            "kvm_machines": 0,
        }
        mock_pods = self.patch(stats, "get_kvm_pods_stats")
        mock_pods.return_value = pods
        metrics = create_metrics(STATS_DEFINITIONS)
        update_prometheus_stats(metrics)
        self.assertThat(
            mock, MockCalledOnce())
        self.assertThat(
            mock_arches, MockCalledOnce())
        self.assertThat(
            mock_pods, MockCalledOnce())

    def test_push_stats_to_prometheus(self):
        factory.make_RegionRackController()
        maas_name = 'random.maas'
        push_gateway = '127.0.0.1:2000'
        mock_prom_cli = self.patch(stats, "prom_cli")
        push_stats_to_prometheus(maas_name, push_gateway)
        self.assertThat(
            mock_prom_cli.push_to_gateway, MockCalledOnceWith(
                push_gateway, job="stats_for_%s" % maas_name,
                registry=mock.ANY))


class TestPrometheusService(MAASTestCase):
    """Tests for `ImportPrometheusService`."""

    def test__is_a_TimerService(self):
        service = stats.PrometheusService()
        self.assertIsInstance(service, TimerService)

    def test__runs_once_an_hour_by_default(self):
        service = stats.PrometheusService()
        self.assertEqual(3600, service.step)

    def test__calls__maybe_make_stats_request(self):
        service = stats.PrometheusService()
        self.assertEqual(
            (service.maybe_push_prometheus_stats, (), {}),
            service.call)

    def test_maybe_make_stats_request_does_not_error(self):
        service = stats.PrometheusService()
        deferToDatabase = self.patch(stats, "deferToDatabase")
        exception_type = factory.make_exception_type()
        deferToDatabase.return_value = fail(exception_type())
        d = service.maybe_push_prometheus_stats()
        self.assertIsNone(extract_result(d))


class TestPrometheusServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `PrometheusService`."""

    def test_maybe_make_stats_request_makes_request(self):
        mock_call = self.patch(stats, "push_stats_to_prometheus")
        self.patch(stats, "PROMETHEUS_SUPPORTED", True)

        with transaction.atomic():
            Config.objects.set_config('prometheus_enabled', True)
            Config.objects.set_config(
                'prometheus_push_gateway', '192.168.1.1:8081')

        service = stats.PrometheusService()
        maybe_push_prometheus_stats = asynchronous(
            service.maybe_push_prometheus_stats)
        maybe_push_prometheus_stats().wait(5)

        self.assertThat(mock_call, MockCalledOnce())

    def test_maybe_make_stats_request_doesnt_make_request(self):
        mock_prom_cli = self.patch(stats, "prom_cli")

        with transaction.atomic():
            Config.objects.set_config('enable_analytics', False)

        service = stats.PrometheusService()
        maybe_push_prometheus_stats = asynchronous(
            service.maybe_push_prometheus_stats)
        maybe_push_prometheus_stats().wait(5)

        self.assertThat(
            mock_prom_cli.push_stats_to_prometheus, MockNotCalled())
