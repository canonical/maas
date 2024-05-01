# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Prometheus integration"""


from datetime import timedelta

from django.db.models import F, Max, Q, Window
from django.http import HttpResponse, HttpResponseNotFound
import prometheus_client
from twisted.application.internet import TimerService

from maasserver.enum import SERVICE_STATUS
from maasserver.models import Config, Event
from maasserver.models.node import RackController
from maasserver.models.service import Service
from maasserver.stats import (
    get_custom_images_deployed_stats,
    get_custom_images_uploaded_stats,
    get_maas_stats,
    get_machines_by_architecture,
    get_subnets_utilisation_stats,
    get_vm_hosts_stats,
    get_vmcluster_stats,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.events import EVENT_TYPES
from provisioningserver.logger import LegacyLogger
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
        "maas_service_availability",
        "Availability of the services running in a rack",
        ["system_id", "service"],
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
    MetricDefinition(
        "Gauge",
        "maas_machines_avg_deployment_time",
        "Average time in seconds of the last successful deployment of all machines",
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
    MetricDefinition(
        "Gauge",
        "maas_custom_static_images_uploaded",
        "Number of custom static OS images uploaded to MAAS",
        ["base_image", "file_type"],
    ),
    MetricDefinition(
        "Gauge",
        "maas_custom_static_images_deployed",
        "Number of custom static OS images deployed",
    ),
    MetricDefinition(
        "Gauge",
        "maas_vmcluster_projects",
        "Number of cluster projects",
    ),
    MetricDefinition(
        "Gauge",
        "maas_vmcluster_hosts",
        "Number of VM hosts in a cluster",
    ),
    MetricDefinition(
        "Gauge",
        "maas_vmcluster_vms",
        "Number of machines in a cluster",
    ),
]

_METRICS = {}


def prometheus_stats_handler(request):
    configs = Config.objects.get_configs(["prometheus_enabled", "uuid"])
    if not configs["prometheus_enabled"]:
        return HttpResponseNotFound()

    global _METRICS
    if not _METRICS:
        _METRICS = create_metrics(
            STATS_DEFINITIONS,
            extra_labels={"maas_id": configs["uuid"]},
            update_handlers=[update_prometheus_stats],
            registry=prometheus_client.CollectorRegistry(),
        )

    return HttpResponse(
        content=_METRICS.generate_latest(), content_type="text/plain"
    )


def update_prometheus_stats(metrics: PrometheusMetrics) -> PrometheusMetrics:
    """Update metrics in a PrometheusMetrics based on database values."""
    stats = get_maas_stats()
    architectures = get_machines_by_architecture()
    vm_hosts = get_vm_hosts_stats()
    vmcluster = get_vmcluster_stats()

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
        metrics.update(f"maas_net_{stype}", "set", value=number)

    # Gather overall amount of machine resources
    for resource, value in stats["machine_stats"].items():
        metrics.update(f"maas_machines_{resource}", "set", value=value)

    # Gather status of the services from all the rack controllers
    service_status_to_int_mapping = {
        SERVICE_STATUS.UNKNOWN: 0,
        SERVICE_STATUS.RUNNING: 1,
        SERVICE_STATUS.DEGRADED: 2,
        SERVICE_STATUS.DEAD: 3,
        SERVICE_STATUS.OFF: 4,
    }
    for rack_controller in RackController.objects.all():
        for service in Service.objects.filter(node=rack_controller).all():
            metrics.update(
                "maas_service_availability",
                "set",
                value=service_status_to_int_mapping[service.status],
                labels={
                    "system_id": rack_controller.system_id,
                    "service": service.name,
                },
            )

    # Gather the time in seconds of the last successful deployment from all
    # machines in MAAS. Metric specifications:
    #   - a machine is not included in the average if that machine is being
    #     deployed
    #   - a machine is not included in the calculation if the last deployment
    #     failed
    #   - if there are no machines with successful deployment time, the metrics
    #     will take NaN as value
    deployment_start_event = EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT
    deployment_end_event = EVENT_TYPES.DEPLOYED
    deployment_events = (
        Event.objects.filter(
            Q(type__name=deployment_end_event)
            | Q(type__name=deployment_start_event),
            node__system_id=F("node_system_id"),
        )
        .annotate(
            start_time=Window(
                expression=Max(
                    "created", filter=Q(type__name=deployment_start_event)
                ),
                partition_by=[F("node_system_id")],
            ),
            end_time=Window(
                expression=Max(
                    "created", filter=Q(type__name=deployment_end_event)
                ),
                partition_by=[F("node_system_id")],
            ),
        )
        .values(
            system_id=F("node_system_id"),
            deployment_time=F("end_time") - F("start_time"),
        )
        .distinct("system_id")
    )
    total_deployment_time = 0
    count_deployed_machines = 0
    for deployment_event in deployment_events:
        deployment_time = deployment_event["deployment_time"]
        is_first_deployment = deployment_time is None
        is_deployment_complete = (
            False if is_first_deployment else deployment_time > timedelta(0)
        )
        if is_deployment_complete:
            total_deployment_time += deployment_time.total_seconds()
            count_deployed_machines += 1
    if count_deployed_machines != 0:
        avg_deployment_time = round(
            total_deployment_time / count_deployed_machines, 1
        )
    else:
        avg_deployment_time = float("nan")
    metrics.update(
        "maas_machines_avg_deployment_time",
        "set",
        value=avg_deployment_time,
    )

    # Gather all stats for vm_hosts
    metrics.update("maas_kvm_pods", "set", value=vm_hosts["vm_hosts"])
    metrics.update("maas_kvm_machines", "set", value=vm_hosts["vms"])
    for metric in ("cores", "memory", "storage"):
        metrics.update(
            f"maas_kvm_{metric}",
            "set",
            value=vm_hosts["available_resources"][metric],
            labels={"status": "available"},
        )
        metrics.update(
            f"maas_kvm_{metric}",
            "set",
            value=vm_hosts["utilized_resources"][metric],
            labels={"status": "used"},
        )
    metrics.update(
        "maas_kvm_overcommit_cores",
        "set",
        value=vm_hosts["available_resources"]["over_cores"],
    )
    metrics.update(
        "maas_kvm_overcommit_memory",
        "set",
        value=vm_hosts["available_resources"]["over_memory"],
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
            metric_name = f"maas_net_subnet_ip_{addr_type}"
            for status in ("available", "used"):
                metrics.update(
                    metric_name,
                    "set",
                    value=stats[f"{addr_type}_{status}"],
                    labels={"cidr": cidr, "status": status},
                )

    for custom_image in get_custom_images_uploaded_stats():
        metrics.update(
            "maas_custom_static_images_uploaded",
            "set",
            value=custom_image.get("count", 0),
            labels={
                "base_image": custom_image["base_image"],
                "file_type": custom_image["filetype"],
            },
        )
    metrics.update(
        "maas_custom_static_images_deployed",
        "set",
        value=get_custom_images_deployed_stats(),
    )

    metrics.update(
        "maas_vmcluster_projects", "set", value=vmcluster["projects"]
    )
    metrics.update("maas_vmcluster_hosts", "set", value=vmcluster["vm_hosts"])
    metrics.update("maas_vmcluster_vms", "set", value=vmcluster["vms"])

    return metrics


def push_stats_to_prometheus(maas_name, push_gateway):
    metrics = create_metrics(
        STATS_DEFINITIONS, registry=prometheus_client.CollectorRegistry()
    )
    update_prometheus_stats(metrics)
    prometheus_client.push_to_gateway(
        push_gateway, job="stats_for_%s" % maas_name, registry=metrics.registry
    )


# Define the default time the service interval is run.
# This can be overriden by the config option.
PROMETHEUS_SERVICE_PERIOD = timedelta(minutes=60)


class PrometheusService(TimerService):
    """Service to periodically push stats to Prometheus

    This will run immediately when it's started, by default, it will run
    every 60 minutes, though the interval can be overridden (see
    prometheus_push_interval global config).
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
                not config["prometheus_enabled"]
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
