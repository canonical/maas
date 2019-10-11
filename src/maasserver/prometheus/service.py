from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.prometheus.resource import PrometheusMetricsResource
from provisioningserver.utils.twisted import reducedWebLogFormatter
from twisted.application.internet import StreamServerEndpointService
from twisted.internet.endpoints import TCP6ServerEndpoint
from twisted.web.resource import Resource
from twisted.web.server import Site


def create_prometheus_exporter_service(reactor, port):
    """Return a service exposing prometheus metrics on the specified port."""
    root = Resource()
    root.putChild(b"metrics", PrometheusMetricsResource(PROMETHEUS_METRICS))
    site = Site(root, logFormatter=reducedWebLogFormatter)
    endpoint = TCP6ServerEndpoint(reactor, port)
    service = StreamServerEndpointService(endpoint, site)
    service.setName("prometheus-exporter")
    return service
