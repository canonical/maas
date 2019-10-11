from provisioningserver.prometheus.utils import PrometheusMetrics
from twisted.web.resource import Resource


class PrometheusMetricsResource(Resource):
    """A resource for exposing prometheus metrics."""

    isLeaf = True

    def __init__(self, prometheus_metrics: PrometheusMetrics):
        self.prometheus_metrics = prometheus_metrics

    def render_GET(self, request):
        content = self.prometheus_metrics.generate_latest()
        if content is None:
            request.setResponseCode(404)
            return b""
        return content
