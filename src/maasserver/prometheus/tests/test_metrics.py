from maasserver.prometheus import (
    metrics,
    prom_cli,
)
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.django_urls import reverse
from maastesting.testcase import MAASTestCase


class TestPrometheusMetrics(MAASTestCase):

    def test_empty(self):
        prometheus_metrics = metrics.PrometheusMetrics()
        self.assertEqual(prometheus_metrics.available_metrics, [])
        self.assertIsNone(prometheus_metrics.generate_latest())

    def test_update_empty(self):
        prometheus_metrics = metrics.PrometheusMetrics()
        prometheus_metrics.update('some_metric', 'inc')
        self.assertIsNone(prometheus_metrics.generate_latest())

    def test_update(self):
        registry = prom_cli.CollectorRegistry()
        metric = prom_cli.Gauge(
            'a_gauge', 'A Gauge', ['foo', 'bar'], registry=registry)
        prometheus_metrics = metrics.PrometheusMetrics(
            registry=registry, metrics={'a_gauge': metric})
        prometheus_metrics.update(
            'a_gauge', 'set', value=22, labels={'foo': 'FOO', 'bar': 'BAR'})
        self.assertIn(
            'a_gauge{bar="BAR",foo="FOO"} 22.0',
            prometheus_metrics.generate_latest().decode('ascii'))


class TestCreateMetrics(MAASTestCase):

    def test_metrics(self):
        prometheus_metrics = metrics.create_metrics()
        self.assertIsInstance(prometheus_metrics, metrics.PrometheusMetrics)
        self.assertEqual(
            prometheus_metrics.available_metrics, ['http_request_latency'])

    def test_metrics_prometheus_not_availble(self):
        self.patch(metrics, 'PROMETHEUS_SUPPORTED', False)
        prometheus_metrics = metrics.create_metrics()
        self.assertEqual(prometheus_metrics.available_metrics, [])


class TestPrometheusMetricsHandler(MAASServerTestCase):

    def test_metrics(self):
        response = self.client.get(reverse('metrics'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'TYPE http_request_latency histogram',
            response.content.decode('ascii'))

    def test_metrics_prometheus_not_available(self):
        self.patch(metrics, 'PROMETHEUS_METRICS', metrics.PrometheusMetrics())
        response = self.client.get(reverse('metrics'))
        self.assertEqual(response.status_code, 404)
