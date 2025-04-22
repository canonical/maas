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
from pathlib import Path

from django.db.models import Case, Count, F, Max, Q, When
import requests
from twisted.application.internet import TimerService

from maasserver.certificates import get_maas_certificate
from maasserver.enum import IPADDRESS_TYPE, MSM_STATUS, NODE_STATUS, NODE_TYPE
from maasserver.models import (
    BMC,
    BootResourceFile,
    Config,
    DHCPSnippet,
    Fabric,
    Machine,
    Node,
    OwnerData,
    Pod,
    Space,
    StaticIPAddress,
    Subnet,
    Tag,
    VLAN,
    VMCluster,
)
from maasserver.models.nodeconfig import NODE_CONFIG_TYPE
from maasserver.models.virtualmachine import get_vm_host_used_resources
from maasserver.msm import msm_status
from maasserver.utils import get_maas_user_agent
from maasserver.utils.orm import NotNullSum, transactional
from maasserver.utils.threads import deferToDatabase
from metadataserver.enum import SCRIPT_STATUS
from provisioningserver.logger import LegacyLogger
from provisioningserver.path import get_maas_data_path
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
)
from provisioningserver.utils.network import IPRANGE_PURPOSE, IPRangeStatistics

log = LegacyLogger()


def get_machine_stats():
    return Machine.objects.filter(
        nodeconfig__name=NODE_CONFIG_TYPE.DISCOVERED
    ).aggregate(
        total_cpu=NotNullSum("cpu_count"),
        total_mem=NotNullSum("memory"),
        total_storage=NotNullSum(
            Case(
                When(
                    nodeconfig__blockdevice__physicalblockdevice__isnull=False,
                    then=F("nodeconfig__blockdevice__size"),
                ),
            )
        ),
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


def count_of(**filters):
    return Count(Case(When(**filters, then=1)))


def get_lxd_initial_auth_stats():
    stats = Pod.objects.filter(power_type="lxd").aggregate(
        trust_password=count_of(created_with_trust_password=True),
        no_trust_password=count_of(created_with_trust_password=False),
        maas_generated_cert=count_of(created_with_maas_generated_cert=True),
        user_provided_cert=count_of(created_with_maas_generated_cert=False),
        expires_in_10_days=count_of(
            created_with_cert_expiration_days__gte=0,
            created_with_cert_expiration_days__lt=10,
        ),
        expires_in_1_month=count_of(
            created_with_cert_expiration_days__gte=10,
            created_with_cert_expiration_days__lt=31,
        ),
        expires_in_3_months=count_of(
            created_with_cert_expiration_days__gte=31,
            created_with_cert_expiration_days__lt=92,
        ),
        expires_in_1_year=count_of(
            created_with_cert_expiration_days__gte=92,
            created_with_cert_expiration_days__lt=366,
        ),
        expires_in_2_years=count_of(
            created_with_cert_expiration_days__gte=366,
            created_with_cert_expiration_days__lt=731,
        ),
        expires_in_3_years=count_of(
            created_with_cert_expiration_days__gte=731,
            created_with_cert_expiration_days__lt=1096,
        ),
        expires_in_10_years=count_of(
            created_with_cert_expiration_days__gte=1096,
            created_with_cert_expiration_days__lt=3653,
        ),
        expires_in_more_than_10_years=count_of(
            created_with_cert_expiration_days__gte=3653,
        ),
    )
    cert_expiration_days = {}
    for key, value in stats.items():
        if not key.startswith("expires_in_"):
            continue
        cert_expiration_days[key[len("expires_in_") :]] = value
    for key in cert_expiration_days:
        del stats["expires_in_" + key]

    stats["cert_expiration_days"] = cert_expiration_days
    return stats


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
            if IPRANGE_PURPOSE.DYNAMIC in rng.purpose:
                dynamic_available += rng.num_addresses
            elif IPRANGE_PURPOSE.RESERVED in rng.purpose:
                reserved_available += rng.num_addresses
            elif IPRANGE_PURPOSE.ASSIGNED_IP in rng.purpose:
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


def get_vmcluster_stats(**filter_params):
    clusters = VMCluster.objects.filter(**filter_params)
    stats = {
        "projects": len(clusters),
        "vm_hosts": 0,
        "vms": 0,
        "available_resources": {
            "cores": 0,
            "memory": 0,
            "over_cores": 0,
            "over_memory": 0,
            "storage_local": 0,
            "storage_shared": 0,
        },
        "utilized_resources": {
            "cores": 0,
            "memory": 0,
            "storage_local": 0,
            "storage_shared": 0,
        },
    }

    for cluster in clusters:
        res = cluster.total_resources()
        stats["vm_hosts"] += res.vmhost_count
        stats["vms"] += res.vm_count.total
        stats["available_resources"]["cores"] += res.cores.total
        stats["available_resources"]["over_cores"] += res.cores.overcommited
        stats["available_resources"]["memory"] += res.memory.general.total
        stats["available_resources"]["over_memory"] += (
            res.memory.general.overcommited
        )
        stats["utilized_resources"]["cores"] += res.cores.allocated
        stats["utilized_resources"]["memory"] += res.memory.general.allocated

        for pool in res.storage_pools.values():
            if pool.shared:
                stats["available_resources"]["storage_shared"] += pool.total
                stats["utilized_resources"]["storage_shared"] += pool.allocated
            else:
                stats["available_resources"]["storage_local"] += pool.total
                stats["utilized_resources"]["storage_local"] += pool.allocated

    return stats


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


def get_storage_layouts_stats():
    counts = (
        Node.objects.exclude(last_applied_storage_layout="")
        .values("last_applied_storage_layout")
        .annotate(count=Count("id"))
    )
    return {
        entry["last_applied_storage_layout"]: entry["count"]
        for entry in counts
    }


def get_tls_configuration_stats():
    cert = get_maas_certificate()
    if not cert:
        return {"tls_enabled": False, "tls_cert_validity_days": None}

    validity_days = None
    expiration = cert.expiration()
    not_before = cert.not_before()
    if all((expiration, not_before)):
        validity_days = (expiration - not_before).days
    return {"tls_enabled": True, "tls_cert_validity_days": validity_days}


def get_bmc_stats():
    stats = (
        BMC.objects.all()
        .values("power_type")
        .annotate(
            auto_detected=count_of(created_by_commissioning=True),
            user_created=count_of(created_by_commissioning__exact=False),
            unknown=count_of(created_by_commissioning__exact=None),
        )
    )
    result = {
        # BMCs that were auto-detected and created by commissoning.
        "auto_detected": {},
        # BMCs that the user manually created.
        "user_created": {},
        # Before 3.2 we didn't track whether the BMC was auto-detected.
        "unknown": {},
    }
    for entry in stats:
        for key in result:
            if entry[key]:
                result[key][entry["power_type"]] = entry[key]
    return result


def get_vault_stats():
    return {"enabled": Config.objects.get_config("vault_enabled", False)}


def get_ansible_stats(path=None):
    n_install = 0
    if not path:
        path = Path(get_maas_data_path(".ansible"))
    if path.is_file():
        n_install += 1
    return {"ansible_installs": n_install}


def get_dhcp_snippets_stats():
    dhcp_snippets = DHCPSnippet.objects.aggregate(
        node_count=Count("pk", filter=(~Q(node=None) & Q(subnet=None))),
        subnet_count=Count("pk", filter=(~Q(subnet=None) & Q(node=None))),
        global_count=Count("pk", filter=(Q(subnet=None) & Q(node=None))),
    )

    return dhcp_snippets


def get_tags_stats():
    return Tag.objects.aggregate(
        total_count=Count("pk"),
        automatic_tag_count=Count("pk", filter=~Q(definition="")),
        with_kernel_opts_count=Count("pk", filter=~Q(kernel_opts="")),
    )


def get_msm_stats():
    status = msm_status()
    if not status:
        return {
            "connected": False,
        }
    return {
        "connected": status["running"] == MSM_STATUS.CONNECTED,
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
    lxd_vm_hosts_stats = get_vm_hosts_stats(power_type="lxd")
    lxd_vm_hosts_stats["initial_auth"] = get_lxd_initial_auth_stats()
    # custom images
    custom_images = get_custom_images_uploaded_stats()

    return {
        "controllers": {
            "regionracks": node_types.get(
                NODE_TYPE.REGION_AND_RACK_CONTROLLER, 0
            ),
            "regions": node_types.get(NODE_TYPE.REGION_CONTROLLER, 0),
            "racks": node_types.get(NODE_TYPE.RACK_CONTROLLER, 0),
        },
        "dhcp_snippets": get_dhcp_snippets_stats(),
        "nodes": {
            "machines": node_types.get(NODE_TYPE.MACHINE, 0),
            "devices": node_types.get(NODE_TYPE.DEVICE, 0),
        },
        "machine_stats": stats,  # count of cpus, mem, storage
        "machine_status": machine_status,  # machines by status
        "network_stats": netstats,  # network status
        "vm_hosts": {
            "lxd": lxd_vm_hosts_stats,
            "virsh": get_vm_hosts_stats(power_type="virsh"),
        },
        "workload_annotations": get_workload_annotations_stats(),
        "brownfield": get_brownfield_stats(),
        "custom_images": {
            "deployed": get_custom_images_deployed_stats(),
            "uploaded": {
                f"{img['base_image']}__{img['filetype']}": img.get("count", 0)
                for img in custom_images
            },
        },
        "vmcluster": get_vmcluster_stats(),
        "storage_layouts": get_storage_layouts_stats(),
        "tls_configuration": get_tls_configuration_stats(),
        "bmcs": get_bmc_stats(),
        "vault": get_vault_stats(),
        "tags": get_tags_stats(),
        # ansible installs?
        "ansible": get_ansible_stats(),
        # enroled in Site Manager?
        "site_manager_connection": get_msm_stats(),
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
