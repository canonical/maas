# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from time import time

from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS


class PrometheusRequestMetricsMiddleware:
    """Middleware to set Prometheus metrics related to HTTP requests."""

    def __init__(self, get_response, prometheus_metrics=PROMETHEUS_METRICS):
        self.get_response = get_response
        self.prometheus_metrics = prometheus_metrics

    def __call__(self, request):
        start_time = time()
        response = self.get_response(request)
        end_time = time()
        self._process_metrics(request, response, start_time, end_time)
        return response

    def _process_metrics(self, request, response, start_time, end_time):
        op = request.POST.get('op', request.GET.get('op', ''))
        labels = {
            'method': request.method,
            'path': request.path,
            'status': response.status_code,
            'op': op
        }

        self.prometheus_metrics.update(
            'maas_http_request_latency', 'observe',
            value=end_time - start_time, labels=labels)
        if not response.streaming:
            self.prometheus_metrics.update(
                'maas_http_response_size', 'observe',
                value=len(response.content), labels=labels)
