from maasserver.prometheus import metrics
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.django_urls import reverse
from maastesting.testcase import MAASTestCase


class TestCreateMetrics(MAASTestCase):

    def test_metrics(self):
        prometheus_metrics = metrics.create_metrics()
        self.assertIsInstance(prometheus_metrics, metrics.PrometheusMetrics)
        self.assertCountEqual(
            prometheus_metrics.metrics.keys(), ['http_request_latency'])

    def test_metrics_prometheus_not_availble(self):
        self.patch(metrics, 'PROMETHEUS_SUPPORTED', False)
        self.assertIsNone(metrics.create_metrics())


class TestPrometheusMetricsHandler(MAASServerTestCase):

    def test_metrics(self):
        response = self.client.get(reverse('metrics'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'TYPE http_request_latency histogram',
            response.content.decode('ascii'))

    def test_metrics_prometheus_not_available(self):
        self.patch(metrics, 'PROMETHEUS_METRICS', None)
        response = self.client.get(reverse('metrics'))
        self.assertEqual(response.status_code, 404)
