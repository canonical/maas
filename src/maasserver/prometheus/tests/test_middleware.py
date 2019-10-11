from django.http import HttpResponse
from maasserver.prometheus.middleware import PrometheusRequestMetricsMiddleware
from maasserver.testing.factory import factory
from maastesting.testcase import MAASTestCase
import prometheus_client
from provisioningserver.prometheus.metrics import METRICS_DEFINITIONS
from provisioningserver.prometheus.utils import create_metrics


class TestPrometheusRequestMetricsMiddleware(MAASTestCase):
    def get_response(self, request):
        status = 200 if request.path.startswith("/MAAS/accounts") else 404
        return HttpResponse(status=status)

    def test_update_metrics(self):
        prometheus_metrics = create_metrics(
            METRICS_DEFINITIONS, registry=prometheus_client.CollectorRegistry()
        )
        middleware = PrometheusRequestMetricsMiddleware(
            self.get_response, prometheus_metrics=prometheus_metrics
        )
        middleware(factory.make_fake_request("/MAAS/accounts/login/"))
        middleware(factory.make_fake_request("/MAAS/accounts/login/"))
        middleware(factory.make_fake_request("/MAAS/other/path"))
        middleware(
            factory.make_fake_request(
                "/MAAS/other/path", data={"op": "do-foo"}
            )
        )
        middleware(
            factory.make_fake_request(
                "/MAAS/other/path", method="POST", data={"op": "do-bar"}
            )
        )
        metrics_text = prometheus_metrics.generate_latest().decode("ascii")
        self.assertIn(
            'maas_http_request_latency_count{method="GET",op="",'
            'path="/MAAS/accounts/login/",status="200"} 2.0',
            metrics_text,
        )
        self.assertIn(
            'maas_http_request_latency_count{method="GET",op="do-foo",'
            'path="/MAAS/other/path",status="404"} 1.0',
            metrics_text,
        )
        self.assertIn(
            'maas_http_request_latency_count{method="POST",op="do-bar",'
            'path="/MAAS/other/path",status="404"} 1.0',
            metrics_text,
        )
        self.assertIn(
            'maas_http_response_size_count{method="GET",op="",'
            'path="/MAAS/accounts/login/",status="200"} 2.0',
            metrics_text,
        )
        self.assertIn(
            'maas_http_response_size_count{method="GET",op="do-foo",'
            'path="/MAAS/other/path",status="404"} 1.0',
            metrics_text,
        )
        self.assertIn(
            'maas_http_response_size_count{method="POST",op="do-bar",'
            'path="/MAAS/other/path",status="404"} 1.0',
            metrics_text,
        )
        self.assertIn(
            'maas_http_request_query_count_count{method="GET",op="",'
            'path="/MAAS/accounts/login/",status="200"} 2.0',
            metrics_text,
        )
