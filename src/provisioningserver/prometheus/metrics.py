# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Prometheus metrics."""

from provisioningserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
)
from provisioningserver.utils.ipaddr import get_machine_default_gateway_ip

_HTTP_REQUEST_LABELS = ["method", "path", "status", "op"]
_WEBSOCKET_CALL_LABELS = ["call"]

METRICS_DEFINITIONS = [
    # rackd metrics
    MetricDefinition(
        "Histogram",
        "maas_rack_region_rpc_call_latency",
        "Latency of Rack-Region RPC call",
        ["call"],
    ),
    MetricDefinition(
        "Histogram",
        "maas_tftp_file_transfer_latency",
        "Latency of TFTP file downloads",
        ["filename"],
    ),
    # regiond metrics
    MetricDefinition(
        "Histogram",
        "maas_http_request_latency",
        "HTTP request latency",
        _HTTP_REQUEST_LABELS,
    ),
    MetricDefinition(
        "Histogram",
        "maas_http_response_size",
        "HTTP response size",
        _HTTP_REQUEST_LABELS,
        buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
    ),
    MetricDefinition(
        "Histogram",
        "maas_http_request_query_count",
        "HTTP request query count",
        _HTTP_REQUEST_LABELS,
        buckets=[10, 25, 50, 100, 200, 500],
    ),
    MetricDefinition(
        "Histogram",
        "maas_http_request_query_latency",
        "HTTP request query latency",
        _HTTP_REQUEST_LABELS,
    ),
    MetricDefinition(
        "Histogram",
        "maas_region_rack_rpc_call_latency",
        "Latency of Region-Rack RPC call",
        ["call"],
    ),
    MetricDefinition(
        "Histogram",
        "maas_websocket_call_latency",
        "Latency of a Websocket handler call",
        ["call"],
    ),
    MetricDefinition(
        "Histogram",
        "maas_websocket_call_query_count",
        "Websocket call query count",
        _WEBSOCKET_CALL_LABELS,
        buckets=[10, 25, 50, 100, 200, 500],
    ),
    MetricDefinition(
        "Histogram",
        "maas_websocket_call_query_latency",
        "HTTP request query latency",
        _WEBSOCKET_CALL_LABELS,
    ),
    MetricDefinition(
        "Counter",
        "maas_virsh_fetch_description_failure",
        "dumpxml failures from virsh",
    ),
    MetricDefinition(
        "Counter",
        "maas_virsh_fetch_mac_failure",
        "domiflist failures from virsh",
    ),
    MetricDefinition(
        "Counter",
        "maas_virsh_storage_pool_creation_failure",
        "domiflist failures from virsh",
    ),
    MetricDefinition(
        "Counter",
        "maas_lxd_disk_creation_failure",
        "failures of LXD disk creation",
    ),
    MetricDefinition(
        "Counter",
        "maas_lxd_fetch_machine_failure",
        "failures for fetching LXD machines",
    ),
    MetricDefinition(
        "Counter",
        "maas_rpc_pool_exhaustion_count",
        """
        counts the number of occurances of the RPC
        connection pool allocate its maxmimum number
        of connections
        """,
    ),
    MetricDefinition(
        "Counter",
        "maas_dns_full_zonefile_write_count",
        """
        counts the number of times MAAS writes
        to a zonefile rather than push a dynamic
        update per DNS zone
        """,
        ["zone"],
    ),
    MetricDefinition(
        "Counter",
        "maas_dns_dynamic_update_count",
        """
        counts the number of times MAAS pushes
        a dynamic update per DNS zone rather than
        writing a zonefile
        """,
        ["zone"],
    ),
    MetricDefinition(
        "Histogram",
        "maas_dns_update_latency",
        "the time it takes MAAS to update BIND",
        ["update_type"],
    ),
]


# Global for tracking global values for metrics label. These are set
# differently from rackd and regiond code, but this is defined here so the
# logic using it can be generic.
GLOBAL_LABELS = {
    # The MAAS installation UUID, the same for all regions/racks within a
    # deployment
    "maas_uuid": None,
}


def set_global_labels(**labels):
    """Update global labels for metrics."""
    global GLOBAL_LABELS
    GLOBAL_LABELS.update(labels)


PROMETHEUS_METRICS = create_metrics(
    METRICS_DEFINITIONS,
    extra_labels={
        "host": get_machine_default_gateway_ip(),
        "maas_id": lambda: GLOBAL_LABELS["maas_uuid"],
    },
)
