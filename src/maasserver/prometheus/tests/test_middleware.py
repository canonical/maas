from django.http import HttpResponse
from maasserver.prometheus import prom_cli
from maasserver.prometheus.metrics import create_metrics
from maasserver.prometheus.middleware import (
    PrometheusRequestMetricsMiddleware,
)
from maasserver.testing.factory import factory
from maastesting.testcase import MAASTestCase


class TestPrometheusRequestMetricsMiddleware(MAASTestCase):

    def get_response(self, request):
        status = 200 if request.path.startswith('/MAAS/accounts') else 404
        return HttpResponse(status=status)

    def test_update_metrics(self):
        prometheus_metrics = create_metrics()
        middleware = PrometheusRequestMetricsMiddleware(
            self.get_response, prometheus_metrics=prometheus_metrics)
        middleware(factory.make_fake_request("/MAAS/accounts/login/"))
        middleware(factory.make_fake_request("/MAAS/accounts/login/"))
        middleware(factory.make_fake_request("/MAAS/other/path"))
        metrics_text = prom_cli.generate_latest(
            prometheus_metrics.registry).decode('ascii')
        self.assertIn(
            'http_request_latency_count{method="GET",'
            'path="/MAAS/accounts/login/",status="200"} 2.0',
            metrics_text)
        self.assertIn(
            'http_request_latency_count{method="GET",'
            'path="/MAAS/other/path",status="404"} 1.0',
            metrics_text)
