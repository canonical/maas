from collections import defaultdict
import json

from django.http import HttpResponse, HttpResponseNotFound
from twisted.application.internet import StreamServerEndpointService
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import TCP6ServerEndpoint
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET, Site

from maasserver.models import Config, Controller
from maasserver.utils.threads import deferToDatabase
from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.prometheus.resource import PrometheusMetricsResource
from provisioningserver.utils.twisted import reducedWebLogFormatter

REGION_PROMETHEUS_PORT = 5239
RACK_PROMETHEUS_PORT = 5249


class PrometheusDiscoveryResource(Resource):
    def _group_controllers_by_az(self, controllers):
        zone_buckets = defaultdict(set)
        for controller in controllers:
            zone_buckets[
                (
                    controller.zone.name,
                    controller.is_region_controller,
                    controller.is_rack_controller,
                )
            ].add(controller)
        return zone_buckets

    def _format(self, bucketed_controllers):
        endpoints = []
        for key, controllers in bucketed_controllers.items():
            print(key)
            zone, is_region, is_rack = key
            instances = [
                ip
                + ":"
                + str(
                    REGION_PROMETHEUS_PORT
                    if is_region
                    else RACK_PROMETHEUS_PORT
                )
                for controller in controllers
                for ip in controller.ip_addresses()
            ]
            if instances:
                endpoints.append(
                    {
                        "targets": instances,
                        "labels": self._get_labels(zone, is_region, is_rack),
                    }
                )
        return endpoints

    def _get_labels(self, zone, is_region, is_rack):
        return {
            "__meta_prometheus_job": "maas",
            "maas_az": zone,
            "maas_region": str(is_region),
            "maas_rack": str(is_rack),
        }

    def _handle_GET(self):
        controllers = Controller.objects.all()
        bucketed_controllers = self._group_controllers_by_az(controllers)
        return self._format(bucketed_controllers)

    def handle_GET(self, request):
        endpoints = self._handle_GET()
        return HttpResponse(
            content=json.dumps(endpoints), content_type="application/json"
        )

    @inlineCallbacks
    def _render_GET(self, request):
        endpoints = yield deferToDatabase(self._handle_GET)
        request.setHeader("Content-Type", "application/json")
        request.write(json.dumps(endpoints).encode("utf-8"))
        request.finish()

    def render_GET(self, request):
        self._render_GET(request)
        return NOT_DONE_YET


def prometheus_discovery_handler(request):
    configs = Config.objects.get_configs(["prometheus_enabled"])
    if not configs["prometheus_enabled"]:
        return HttpResponseNotFound()

    return PrometheusDiscoveryResource().handle_GET(request)


def create_prometheus_exporter_service(reactor, port):
    """Return a service exposing prometheus metrics on the specified port."""
    root = Resource()
    root.putChild(b"metrics", PrometheusMetricsResource(PROMETHEUS_METRICS))
    root.putChild(b"metrics_endpoints", PrometheusDiscoveryResource())
    site = Site(root, logFormatter=reducedWebLogFormatter)
    endpoint = TCP6ServerEndpoint(reactor, port)
    service = StreamServerEndpointService(endpoint, site)
    service.setName("prometheus-exporter")
    return service
