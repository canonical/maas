# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resources."""

__all__ = [
    "get_subnets_utilisation_stats",
    "StatsService",
    "STATS_SERVICE_PERIOD",
]

import base64
from collections import Counter, defaultdict
from datetime import timedelta
import json

from django.db.models import Count, F, Max
import requests
from twisted.application.internet import TimerService

from maasserver.enum import (
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.models import (
    BootResourceFile,
    Config,
    Fabric,
    Machine,
    Node,
    OwnerData,
    Pod,
    Space,
    StaticIPAddress,
    Subnet,
    VLAN,
)
from maasserver.models.virtualmachine import get_vm_host_used_resources
from maasserver.utils import get_maas_user_agent
from maasserver.utils.orm import NotNullSum, transactional
from maasserver.utils.threads import deferToDatabase
from metadataserver.enum import SCRIPT_STATUS
from provisioningserver.logger import LegacyLogger
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
)
from provisioningserver.utils.network import IPRangeStatistics

log = LegacyLogger()


def get_machine_stats():
    # Rather overall amount of stats for machines.
    return Machine.objects.aggregate(
        total_cpu=NotNullSum("cpu_count"),
        total_mem=NotNullSum("memory"),
        total_storage=NotNullSum("blockdevice__size"),
    )


def get_machine_state_stats():
    node_status = (
        Node.objects.filter(
            node_type=NODE_TYPE.MACHINE,
        )
        .values_list("status")
        .annotate(count=Count("status"))
    )
    node_status = defaultdict(int, node_status)
    statuses = (
        "new",
        "ready",
        "allocated",
        "deployed",
        "commissioning",
        "testing",
        "deploying",
        "failed_deployment",
        "failed_commissioning",
        "failed_testing",
        "broken",
    )
    return {
        status: node_status[getattr(NODE_STATUS, status.upper())]
        for status in statuses
    }


def get_machines_by_architecture():
    node_arches = Machine.objects.extra(
        dict(short_arch="SUBSTRING(architecture FROM '(.*)/')")
    ).values_list("short_arch", flat=True)
    return Counter(node_arches)


def get_vm_hosts_stats(**filter_params):
    vm_hosts = Pod.objects.filter(**filter_params)
    # Calculate available physical resources
    # total_mem is in MB
    # local_storage is in bytes
    available_resources = vm_hosts.aggregate(
        cores=NotNullSum("cores"),
        memory=NotNullSum("memory"),
        storage=NotNullSum("local_storage"),
    )

    # available resources with overcommit
    over_cores = over_memory = 0
    for vm_host in vm_hosts:
        over_cores += vm_host.cores * vm_host.cpu_over_commit_ratio
        over_memory += vm_host.memory * vm_host.memory_over_commit_ratio
    available_resources["over_cores"] = over_cores
    available_resources["over_memory"] = over_memory

    # Calculate utilization
    vms = cores = memory = storage = 0
    for vm_host in vm_hosts:
        vms += Node.objects.filter(bmc__id=vm_host.id).count()
        used_resources = get_vm_host_used_resources(vm_host)
        cores += used_resources.cores
        memory += used_resources.total_memory
        storage += used_resources.storage

    return {
        "vm_hosts": len(vm_hosts),
        "vms": vms,
        "available_resources": available_resources,
        "utilized_resources": {
            "cores": cores,
            "memory": memory,
            "storage": storage,
        },
    }


def get_subnets_stats():
    subnets = Subnet.objects.all()
    v4 = [net for net in subnets if net.get_ip_version() == 4]
    v6 = [net for net in subnets if net.get_ip_version() == 6]
    return {
        "spaces": Space.objects.count(),
        "fabrics": Fabric.objects.count(),
        "vlans": VLAN.objects.count(),
        "subnets_v4": len(v4),
        "subnets_v6": len(v6),
    }


def get_subnets_utilisation_stats():
    """Return a dict mapping subnet CIDRs to their utilisation details."""
    ips_count = _get_subnets_ipaddress_count()

    stats = {}
    for subnet in Subnet.objects.all():
        full_range = subnet.get_iprange_usage()
        range_stats = IPRangeStatistics(subnet.get_iprange_usage())
        static = 0
        reserved_available = 0
        reserved_used = 0
        dynamic_available = 0
        dynamic_used = 0
        for rng in full_range.ranges:
            if IPRANGE_TYPE.DYNAMIC in rng.purpose:
                dynamic_available += rng.num_addresses
            elif IPRANGE_TYPE.RESERVED in rng.purpose:
                reserved_available += rng.num_addresses
            elif "assigned-ip" in rng.purpose:
                static += rng.num_addresses
        # allocated IPs
        subnet_ips = ips_count[subnet.id]
        reserved_used += subnet_ips[IPADDRESS_TYPE.USER_RESERVED]
        reserved_available -= reserved_used
        dynamic_used += (
            subnet_ips[IPADDRESS_TYPE.AUTO]
            + subnet_ips[IPADDRESS_TYPE.DHCP]
            + subnet_ips[IPADDRESS_TYPE.DISCOVERED]
        )
        dynamic_available -= dynamic_used
        stats[subnet.cidr] = {
            "available": range_stats.num_available,
            "unavailable": range_stats.num_unavailable,
            "dynamic_available": dynamic_available,
            "dynamic_used": dynamic_used,
            "static": static,
            "reserved_available": reserved_available,
            "reserved_used": reserved_used,
        }
    return stats


def _get_subnets_ipaddress_count():
    counts = defaultdict(lambda: defaultdict(int))
    rows = (
        StaticIPAddress.objects.values("subnet_id", "alloc_type")
        .filter(ip__isnull=False)
        .annotate(count=Count("ip"))
    )
    for row in rows:
        counts[row["subnet_id"]][row["alloc_type"]] = row["count"]
    return counts


def get_workload_annotations_stats():
    return OwnerData.objects.aggregate(
        annotated_machines=Count("node", distinct=True),
        total_annotations=Count("id"),
        unique_keys=Count("key", distinct=True),
        unique_values=Count("value", distinct=True),
    )


def get_custom_images_uploaded_stats():
    return (
        BootResourceFile.objects.exclude(
            resource_set__resource__base_image="",
        )
        .values(
            "filetype",
        )
        .distinct()
        .annotate(
            count=Count("resource_set__resource__base_image"),
            base_image=F("resource_set__resource__base_image"),
        )
    )


def get_custom_images_deployed_stats():
    return Machine.objects.filter(osystem="custom").count()


def get_brownfield_stats():
    deployed_machines = Machine.objects.filter(
        dynamic=False,
        status=NODE_STATUS.DEPLOYED,
    )
    brownfield_machines = deployed_machines.filter(
        current_installation_script_set__isnull=True,
    )
    no_brownfield_machines = Machine.objects.filter(
        current_installation_script_set__isnull=False,
    ).annotate(
        latest_installation_script_date=Max(
            "current_installation_script_set__scriptresult__updated"
        ),
        latest_commissioning_script_date=Max(
            "current_commissioning_script_set__scriptresult__updated"
        ),
    )

    return {
        "machines_added_deployed_with_bmc": brownfield_machines.filter(
            bmc__isnull=False
        ).count(),
        "machines_added_deployed_without_bmc": brownfield_machines.filter(
            bmc__isnull=True
        ).count(),
        "commissioned_after_deploy_brownfield": brownfield_machines.filter(
            current_commissioning_script_set__scriptresult__script_name=COMMISSIONING_OUTPUT_NAME,
            current_commissioning_script_set__scriptresult__status=SCRIPT_STATUS.PASSED,
        ).count(),
        "commissioned_after_deploy_no_brownfield": no_brownfield_machines.filter(
            latest_commissioning_script_date__gt=F(
                "latest_installation_script_date"
            ),
        ).count(),
    }


def get_maas_stats():
    # TODO
    # - architectures
    # - resource pools
    # - pods
    # Get all node types to get count values
    node_types = Node.objects.values_list("node_type", flat=True)
    node_types = Counter(node_types)
    # get summary of machine resources, and its statuses.
    stats = get_machine_stats()
    machine_status = get_machine_state_stats()
    # get summary of network objects
    netstats = get_subnets_stats()

    return {
        "controllers": {
            "regionracks": node_types.get(
                NODE_TYPE.REGION_AND_RACK_CONTROLLER, 0
            ),
            "regions": node_types.get(NODE_TYPE.REGION_CONTROLLER, 0),
            "racks": node_types.get(NODE_TYPE.RACK_CONTROLLER, 0),
        },
        "nodes": {
            "machines": node_types.get(NODE_TYPE.MACHINE, 0),
            "devices": node_types.get(NODE_TYPE.DEVICE, 0),
        },
        "machine_stats": stats,  # count of cpus, mem, storage
        "machine_status": machine_status,  # machines by status
        "network_stats": netstats,  # network status
        "vm_hosts": {
            "lxd": get_vm_hosts_stats(power_type="lxd"),
            "virsh": get_vm_hosts_stats(power_type="virsh"),
        },
        "workload_annotations": get_workload_annotations_stats(),
        "brownfield": get_brownfield_stats(),
    }


def get_request_params():
    data = json.dumps(json.dumps(get_maas_stats()))
    return {"data": base64.b64encode(data.encode()).decode()}


def make_maas_user_agent_request():
    headers = {"User-Agent": get_maas_user_agent()}
    params = get_request_params()
    try:
        requests.get(
            "https://stats.images.maas.io/", params=params, headers=headers
        )
    except Exception:
        # Do not fail if for any reason requests does.
        pass


# How often the import service runs.
STATS_SERVICE_PERIOD = timedelta(hours=24)


class StatsService(TimerService):
    """Service to periodically get stats.

    This will run immediately when it's started, then once again every
    24 hours, though the interval can be overridden by passing it to
    the constructor.
    """

    def __init__(self, interval=STATS_SERVICE_PERIOD):
        super().__init__(
            interval.total_seconds(), self.maybe_make_stats_request
        )

    def maybe_make_stats_request(self):
        def determine_stats_request():
            if Config.objects.get_config("enable_analytics"):
                make_maas_user_agent_request()

        d = deferToDatabase(transactional(determine_stats_request))
        d.addErrback(log.err, "Failure performing user agent request.")
        return d
