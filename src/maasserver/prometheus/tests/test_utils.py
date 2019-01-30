from maasserver.prometheus import (
    prom_cli,
    utils,
)
from maasserver.prometheus.metrics import METRICS_DEFINITIONS
from maastesting.testcase import MAASTestCase


class TestPrometheusMetrics(MAASTestCase):

    def test_empty(self):
        prometheus_metrics = utils.PrometheusMetrics()
        self.assertEqual(prometheus_metrics.available_metrics, [])
        self.assertIsNone(prometheus_metrics.generate_latest())

    def test_update_empty(self):
        prometheus_metrics = utils.PrometheusMetrics()
        prometheus_metrics.update('some_metric', 'inc')
        self.assertIsNone(prometheus_metrics.generate_latest())

    def test_update(self):
        registry = prom_cli.CollectorRegistry()
        metric = prom_cli.Gauge(
            'a_gauge', 'A Gauge', ['foo', 'bar'], registry=registry)
        prometheus_metrics = utils.PrometheusMetrics(
            registry=registry, metrics={'a_gauge': metric})
        prometheus_metrics.update(
            'a_gauge', 'set', value=22, labels={'foo': 'FOO', 'bar': 'BAR'})
        self.assertIn(
            'a_gauge{bar="BAR",foo="FOO"} 22.0',
            prometheus_metrics.generate_latest().decode('ascii'))


class TestCreateMetrics(MAASTestCase):

    def test_metrics(self):
        prometheus_metrics = utils.create_metrics(METRICS_DEFINITIONS)
        self.assertIsInstance(prometheus_metrics, utils.PrometheusMetrics)
        self.assertEqual(
            prometheus_metrics.available_metrics, ['http_request_latency'])

    def test_metrics_prometheus_not_availble(self):
        self.patch(utils, 'PROMETHEUS_SUPPORTED', False)
        prometheus_metrics = utils.create_metrics(METRICS_DEFINITIONS)
        self.assertEqual(prometheus_metrics.available_metrics, [])
