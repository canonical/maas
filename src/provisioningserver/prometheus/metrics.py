# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Prometheus metrics."""

from provisioningserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
)


METRICS_DEFINITIONS = [
    MetricDefinition(
        'Histogram', 'maas_rack_region_rpc_call_latency',
        'Latency of Rack-Region RPC call', ['call']),
    MetricDefinition(
        'Histogram', 'maas_tftp_file_transfer_latency',
        'Latency of TFTP file downloads', ['filename']),
]


PROMETHEUS_METRICS = create_metrics(METRICS_DEFINITIONS)
