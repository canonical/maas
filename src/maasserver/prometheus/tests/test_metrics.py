from maasserver.prometheus import metrics
from maasserver.prometheus.utils import PrometheusMetrics
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.django_urls import reverse


class TestPrometheusMetricsHandler(MAASServerTestCase):

    def test_metrics(self):
        response = self.client.get(reverse('metrics'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('ascii')
        # metrics are included
        self.assertIn(
            'TYPE http_request_latency histogram', content)
        # stats are included too
        self.assertIn('TYPE machine_status gauge', content)

    def test_stats_updated(self):
        factory.make_Node()
        response = self.client.get(reverse('metrics'))
        content = response.content.decode('ascii')
        self.assertIn('machine_status{status="new"} 1.0', content)
        factory.make_Node()
        response = self.client.get(reverse('metrics'))
        content = response.content.decode('ascii')
        self.assertIn('machine_status{status="new"} 2.0', content)

    def test_metrics_prometheus_not_available(self):
        self.patch(metrics, 'PROMETHEUS_METRICS', PrometheusMetrics())
        response = self.client.get(reverse('metrics'))
        self.assertEqual(response.status_code, 404)
