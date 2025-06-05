from twisted.web.resource import Resource

from provisioningserver.prometheus.utils import PrometheusMetrics


class PrometheusMetricsResource(Resource):
    """A resource for exposing prometheus metrics."""

    isLeaf = True

    def __init__(self, prometheus_metrics: PrometheusMetrics):
        self.prometheus_metrics = prometheus_metrics

    def render_GET(self, request):
        request.setHeader(b"Content-Type", b"text/plain")
        content = self.prometheus_metrics.generate_latest()
        if content is None:
            request.setResponseCode(404)
            return b""
        return content
