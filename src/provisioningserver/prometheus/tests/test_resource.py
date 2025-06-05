from unittest.mock import MagicMock

import prometheus_client
from twisted.web.server import Request
from twisted.web.test.test_web import DummyChannel

from maastesting.testcase import MAASTestCase
from provisioningserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
)
from provisioningserver.rackdservices import http


class TestPrometheusMetricsResource(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.metrics_definitions = [
            MetricDefinition(
                "Histogram", "sample_histogram", "Sample histogram", []
            ),
            MetricDefinition(
                "Counter", "sample_counter", "Sample counter", []
            ),
        ]

    def test_metrics(self):
        prometheus_metrics = create_metrics(
            self.metrics_definitions,
            registry=prometheus_client.CollectorRegistry(),
        )
        resource = http.PrometheusMetricsResource(prometheus_metrics)
        request = Request(DummyChannel(), False)
        content = resource.render_GET(request).decode("utf-8")
        self.assertEqual(request.code, 200)
        self.assertIn("TYPE sample_histogram histogram", content)
        self.assertIn("TYPE sample_counter_total counter", content)

    def test_metrics_disabled(self):
        prometheus_metrics = create_metrics(
            None, registry=prometheus_client.CollectorRegistry()
        )
        resource = http.PrometheusMetricsResource(prometheus_metrics)
        request = Request(DummyChannel(), False)
        content = resource.render_GET(request).decode("utf-8")
        self.assertEqual(request.code, 404)
        self.assertEqual(content, "")

    def test_content_type(self):
        prometheus_metrics = create_metrics(
            None, registry=prometheus_client.CollectorRegistry()
        )
        resource = http.PrometheusMetricsResource(prometheus_metrics)
        request = MagicMock()
        resource.render_GET(request)
        request.setHeader.assert_called_with(b"Content-Type", b"text/plain")
