# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Prometheus integration"""


from datetime import timedelta
import json

from django.http import HttpResponse, HttpResponseNotFound
from twisted.application.internet import TimerService

from maasserver.models import Config
from maasserver.stats import (
    get_kvm_pods_stats,
    get_maas_stats,
    get_machines_by_architecture,
    get_subnets_utilisation_stats,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.prometheus import prom_cli, PROMETHEUS_SUPPORTED
from provisioningserver.prometheus.utils import (
    create_metrics,
    MetricDefinition,
    PrometheusMetrics,
)

log = LegacyLogger()

STATS_DEFINITIONS = [
    MetricDefinition(
        "Gauge", "maas_machines", "Number of machines by status", ["status"]
    ),
    MetricDefinition(
        "Gauge",
        "maas_nodes",
        "Number of nodes per type (e.g. racks, machines, etc)",
        ["type"],
    ),
    MetricDefinition("Gauge", "maas_net_spaces", "Number of network spaces"),
    MetricDefinition("Gauge", "maas_net_fabrics", "Number of network fabrics"),
    MetricDefinition("Gauge", "maas_net_vlans", "Number of network VLANs"),
    MetricDefinition("Gauge", "maas_net_subnets_v4", "Number of IPv4 subnets"),
    MetricDefinition("Gauge", "maas_net_subnets_v6", "Number of IPv6 subnets"),
    MetricDefinition(
        "Gauge",
        "maas_net_subnet_ip_count",
        "Number of IPs in a subnet by status",
        ["cidr", "status"],
    ),
    MetricDefinition(
        "Gauge",
        "maas_net_subnet_ip_dynamic",
        "Number of used IPs in a subnet",
        ["cidr", "status"],
    ),
    MetricDefinition(
        "Gauge",
        "maas_net_subnet_ip_reserved",
        "Number of used IPs in a subnet",
        ["cidr", "status"],
    ),
    MetricDefinition(
        "Gauge",
        "maas_net_subnet_ip_static",
        "Number of used IPs in a subnet",
        ["cidr"],
    ),
    MetricDefinition(
        "Gauge",
        "maas_machines_total_mem",
        "Amount of combined memory for all machines",
    ),
    MetricDefinition(
        "Gauge",
        "maas_machines_total_cpu",
        "Amount of combined CPU counts for all machines",
    ),
    MetricDefinition(
        "Gauge",
        "maas_machines_total_storage",
        "Amount of combined storage for all machines",
    ),
    MetricDefinition("Gauge", "maas_kvm_pods", "Number of KVM pods"),
    MetricDefinition(
        "Gauge", "maas_kvm_machines", "Number of KVM virtual machines"
    ),
    MetricDefinition(
        "Gauge", "maas_kvm_cores", "Number of KVM cores", ["status"]
    ),
    MetricDefinition(
        "Gauge", "maas_kvm_memory", "Memory for KVM pods", ["status"]
    ),
    MetricDefinition(
        "Gauge", "maas_kvm_storage", "Size of storage for KVM pods", ["status"]
    ),
    MetricDefinition(
        "Gauge",
        "maas_kvm_overcommit_cores",
        "Number of KVM cores with overcommit",
    ),
    MetricDefinition(
        "Gauge",
        "maas_kvm_overcommit_memory",
        "KVM memory size with overcommit",
    ),
    MetricDefinition(
        "Gauge",
        "maas_machine_arches",
        "Number of machines per architecture",
        ["arches"],
    ),
]

_METRICS = {}


def prometheus_stats_handler(request):
    configs = Config.objects.get_configs(["prometheus_enabled", "uuid"])
    have_prometheus = PROMETHEUS_SUPPORTED and configs["prometheus_enabled"]
    if not have_prometheus:
        return HttpResponseNotFound()

    global _METRICS
    if not _METRICS:
        _METRICS = create_metrics(
            STATS_DEFINITIONS,
            extra_labels={"maas_id": configs["uuid"]},
            update_handlers=[update_prometheus_stats],
            registry=prom_cli.CollectorRegistry(),
        )

    return HttpResponse(
        content=_METRICS.generate_latest(), content_type="text/plain"
    )


def update_prometheus_stats(metrics: PrometheusMetrics):
    """Update metrics in a PrometheusMetrics based on database values."""
    stats = json.loads(get_maas_stats())
    architectures = get_machines_by_architecture()
    pods = get_kvm_pods_stats()

    # Gather counter for machines per status
    for status, machines in stats["machine_status"].items():
        metrics.update(
            "maas_machines", "set", value=machines, labels={"status": status}
        )

    # Gather counter for number of nodes (controllers/machine/devices)
    for ctype, number in stats["controllers"].items():
        metrics.update(
            "maas_nodes", "set", value=number, labels={"type": ctype}
        )
    for ctype, number in stats["nodes"].items():
        metrics.update(
            "maas_nodes", "set", value=number, labels={"type": ctype}
        )

    # Gather counter for networks
    for stype, number in stats["network_stats"].items():
        metrics.update("maas_net_{}".format(stype), "set", value=number)

    # Gather overall amount of machine resources
    for resource, value in stats["machine_stats"].items():
        metrics.update("maas_machines_{}".format(resource), "set", value=value)

    # Gather all stats for pods
    metrics.update("maas_kvm_pods", "set", value=pods["kvm_pods"])
    metrics.update("maas_kvm_machines", "set", value=pods["kvm_machines"])
    for metric in ("cores", "memory", "storage"):
        metrics.update(
            "maas_kvm_{}".format(metric),
            "set",
            value=pods["kvm_available_resources"][metric],
            labels={"status": "available"},
        )
        metrics.update(
            "maas_kvm_{}".format(metric),
            "set",
            value=pods["kvm_utilized_resources"][metric],
            labels={"status": "used"},
        )
    metrics.update(
        "maas_kvm_overcommit_cores",
        "set",
        value=pods["kvm_available_resources"]["over_cores"],
    )
    metrics.update(
        "maas_kvm_overcommit_memory",
        "set",
        value=pods["kvm_available_resources"]["over_memory"],
    )

    # Gather statistics for architectures
    if len(architectures.keys()) > 0:
        for arch, machines in architectures.items():
            metrics.update(
                "maas_machine_arches",
                "set",
                value=machines,
                labels={"arches": arch},
            )

    # Update metrics for subnets
    for cidr, stats in get_subnets_utilisation_stats().items():
        for status in ("available", "unavailable"):
            metrics.update(
                "maas_net_subnet_ip_count",
                "set",
                value=stats[status],
                labels={"cidr": cidr, "status": status},
            )
        metrics.update(
            "maas_net_subnet_ip_static",
            "set",
            value=stats["static"],
            labels={"cidr": cidr},
        )
        for addr_type in ("dynamic", "reserved"):
            metric_name = "maas_net_subnet_ip_{}".format(addr_type)
            for status in ("available", "used"):
                metrics.update(
                    metric_name,
                    "set",
                    value=stats["{}_{}".format(addr_type, status)],
                    labels={"cidr": cidr, "status": status},
                )

    return metrics


def push_stats_to_prometheus(maas_name, push_gateway):
    metrics = create_metrics(
        STATS_DEFINITIONS, registry=prom_cli.CollectorRegistry()
    )
    update_prometheus_stats(metrics)
    prom_cli.push_to_gateway(
        push_gateway, job="stats_for_%s" % maas_name, registry=metrics.registry
    )


# Define the default time the service interval is run.
# This can be overriden by the config option.
PROMETHEUS_SERVICE_PERIOD = timedelta(minutes=60)


class PrometheusService(TimerService, object):
    """Service to periodically push stats to Prometheus

    This will run immediately when it's started, by default, it will run
    every 60 minutes, though the interval can be overridden (see
    prometheus_push_internval global config).
    """

    def __init__(self, interval=PROMETHEUS_SERVICE_PERIOD):
        super().__init__(
            interval.total_seconds(), self.maybe_push_prometheus_stats
        )

    def maybe_push_prometheus_stats(self):
        def determine_stats_request():
            config = Config.objects.get_configs(
                [
                    "maas_name",
                    "prometheus_enabled",
                    "prometheus_push_gateway",
                    "prometheus_push_interval",
                ]
            )
            # Update interval
            self._update_interval(
                timedelta(minutes=config["prometheus_push_interval"])
            )
            # Determine if we can run the actual update.
            if (
                not PROMETHEUS_SUPPORTED
                or not config["prometheus_enabled"]
                or config["prometheus_push_gateway"] is None
            ):
                return
            # Run updates.
            push_stats_to_prometheus(
                config["maas_name"], config["prometheus_push_gateway"]
            )

        d = deferToDatabase(transactional(determine_stats_request))
        d.addErrback(log.err, "Failure pushing stats to prometheus gateway")
        return d

    def _update_interval(self, interval):
        """Change the update interval."""
        interval_seconds = interval.total_seconds()
        if self.step == interval_seconds:
            return
        self._loop.interval = self.step = interval_seconds
        if self._loop.running:
            self._loop.reset()
