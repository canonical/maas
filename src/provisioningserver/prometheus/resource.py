from provisioningserver.prometheus.utils import PrometheusMetrics
from twisted.web import resource


class PrometheusMetricsResource(resource.Resource):
    """A resource for exposing prometheus metrics. """

    isLeaf = True

    def __init__(self, prometheus_metrics: PrometheusMetrics):
        self.prometheus_metrics = prometheus_metrics

    def render_GET(self, request):
        content = self.prometheus_metrics.generate_latest()
        if content is None:
            return resource.NoResource()
        return content
