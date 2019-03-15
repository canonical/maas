# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Prometheus metrics."""

from provisioningserver.prometheus.collectors import (
    node_metrics_definitions,
    update_cpu_metrics,
    update_memory_metrics,
)
from provisioningserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
)
from provisioningserver.utils.ipaddr import get_machine_default_gateway_ip


METRICS_DEFINITIONS = [
    # rackd metrics
    MetricDefinition(
        'Histogram', 'maas_rack_region_rpc_call_latency',
        'Latency of Rack-Region RPC call', ['call']),
    MetricDefinition(
        'Histogram', 'maas_tftp_file_transfer_latency',
        'Latency of TFTP file downloads', ['filename']),
    # regiond metrics
    MetricDefinition(
        'Histogram', 'maas_http_request_latency', 'HTTP request latency',
        ['method', 'path', 'status', 'op']),
    MetricDefinition(
        'Histogram', 'maas_http_response_size', 'HTTP response size',
        ['method', 'path', 'status', 'op'],
        buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]),
    MetricDefinition(
        'Histogram', 'maas_http_request_query_count',
        'HTTP request query count', ['method', 'path', 'status', 'op'],
        buckets=[10, 25, 50, 100, 200, 500]),
    MetricDefinition(
        'Histogram', 'maas_http_request_query_latency',
        'HTTP request query latency', ['method', 'path', 'status', 'op']),
    MetricDefinition(
        'Histogram', 'maas_region_rack_rpc_call_latency',
        'Latency of Region-Rack RPC call', ['call']),
    MetricDefinition(
        'Histogram', 'maas_websocket_call_latency',
        'Latency of a Websocket handler call', ['call']),
    # Common metrics
    *node_metrics_definitions()
]


PROMETHEUS_METRICS = create_metrics(
    METRICS_DEFINITIONS,
    extra_labels={
        'host': get_machine_default_gateway_ip
    },
    update_handlers=[update_cpu_metrics, update_memory_metrics])
