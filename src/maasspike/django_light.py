from collections.abc import Iterable
from itertools import chain
import logging

from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db.models import (
    Case,
    CharField,
    Count,
    Exists,
    FloatField,
    Func,
    OuterRef,
    Q,
    Subquery,
    Sum,
    TextField,
    When,
)
from django.db.models.expressions import F, Value
from django.db.models.functions import Cast, Coalesce, Concat

from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    SIMPLIFIED_NODE_STATUS,
    SIMPLIFIED_NODE_STATUSES_MAP,
)
from maasserver.models import Event, Node, StaticIPAddress
from metadataserver.enum import HARDWARE_TYPE, RESULT_TYPE, SCRIPT_STATUS


def JSONBBuildObject(fields_map):
    fields = chain(*((Value(key), value) for key, value in fields_map.items()))
    return Func(
        *fields, function="jsonb_build_object", output_field=JSONField()
    )


def EnumValues(field, values_map, output_field=None, default=None):
    return Case(
        *(
            When(
                **{
                    f"{field}__in"
                    if isinstance(field_value, Iterable)
                    else field: field_value,
                    "then": Value(value),
                }
            )
            for field_value, value in dict(values_map).items()
        ),
        default=default,
        output_field=output_field,
    )


def Float(field):
    return Cast(field, output_field=FloatField())


TESTING_STATUSES_MAP = {
    SCRIPT_STATUS.PENDING: "pending",
    SCRIPT_STATUS.RUNNING: "running",
    (SCRIPT_STATUS.PASSED, SCRIPT_STATUS.SKIPPED): "passed",
}

TESTING_STATUSES = list(TESTING_STATUSES_MAP.values()) + ["failed"]


Machines = Node.objects.filter(node_type=NODE_TYPE.MACHINE)


def list_machines(admin, limit=None):
    machines_qs = Machines.order_by("id")
    if limit is None:
        machine_ids = None
    else:
        machine_ids = list(machines_qs.values_list("id", flat=True)[:limit])
        machines_qs = machines_qs.filter(id__in=machine_ids)

    entries = _get_machines_qs(machines_qs, admin.is_superuser)
    storage_entries = _get_storage_qs(machines_qs)
    network_entries = _get_network_qs(machines_qs)
    testing_entries = _get_testing_qs(machines_qs)
    extra_macs_entries = _get_extra_macs_qs(machines_qs)

    ipaddress_data = _get_ipaddress_data(machine_ids=machine_ids)

    result = []
    # entries match in both querysets because of ordering by ID and containing
    # all results
    all_entries = zip(
        entries,
        storage_entries,
        network_entries,
        testing_entries,
        extra_macs_entries,
    )
    for (
        entry,
        storage_entry,
        network_entry,
        testing_entry,
        extra_macs_entry,
    ) in all_entries:
        entry |= (
            storage_entry | network_entry | testing_entry | extra_macs_entry
        )

        entry["ip_addresses"] = ipaddress_data.get(entry["id"], [])
        result.append(entry)
    return result


def _get_machines_qs(machines_qs, is_superuser):
    user_permissions = ["edit", "delete"] if is_superuser else []
    return machines_qs.values(
        "architecture",
        "cpu_count",
        "description",
        "distro_series",
        "error_description",
        "hostname",
        "id",
        "locked",
        "osystem",
        "power_state",
        "system_id",
    ).annotate(
        owner=Coalesce("owner__username", Value("")),
        parent=F("parent__system_id"),
        pxe_mac=F("boot_interface__mac_address"),
        fqdn=Concat(
            F("hostname"),
            Value("."),
            F("domain__name"),
            output_field=TextField(),
        ),
        vlan=JSONBBuildObject(
            {
                "id": F("boot_interface__vlan_id"),
                "name": Coalesce(
                    F("boot_interface__vlan__name"), Value("None")
                ),
                "fabric_id": F("boot_interface__vlan__fabric_id"),
                "fabric_name": Coalesce(
                    "boot_interface__vlan__fabric__name",
                    Concat(
                        Value("fabric-"), F("id"), output_field=CharField()
                    ),
                ),
            }
        ),
        status_code=F("status"),
        simple_status=EnumValues(
            "status",
            {
                tuple(statuses): simplified_status
                for simplified_status, statuses in SIMPLIFIED_NODE_STATUSES_MAP.items()
            },
            default=Value(SIMPLIFIED_NODE_STATUS.OTHER),
            output_field=TextField(),
        ),
        status=EnumValues("status", NODE_STATUS_CHOICES_DICT),
        memory=Float(F("memory")) / Value(1024),
        tags=ArrayAgg("tags", distinct=True),
        link_type=Value("machine"),
        power_type=F("bmc__power_type"),
        zone=JSONBBuildObject({"id": "zone__id", "name": "zone__name"}),
        pool=JSONBBuildObject({"id": "pool__id", "name": "pool__name"}),
        domain=JSONBBuildObject({"id": "domain__id", "name": "domain__name"}),
        status_message=Subquery(
            Event.objects.filter(
                node=OuterRef("pk"), type__level__gte=logging.INFO
            )
            .order_by("-created", "-id")
            .annotate(
                message=Concat(
                    F("type__description"),
                    Value(" - "),
                    F("description"),
                    output_field=TextField(),
                ),
            )
            .values("message")[:1]
        ),
        permissions=Case(
            When(
                locked=True,
                then=Value([], output_field=ArrayField(TextField())),
            ),
            default=Value(
                user_permissions, output_field=ArrayField(TextField())
            ),
        ),
    )


def _get_storage_qs(machines):
    return machines.annotate(
        physical_disk_count=Count(
            "current_config__blockdevice__physicalblockdevice",
        ),
        storage=Float(
            Sum(
                "current_config__blockdevice__physicalblockdevice__size",
                default=0,
            ),
        )
        / Value(1000**3),
    ).values("physical_disk_count", "storage")


def _get_network_qs(machines):
    return machines.annotate(
        fabrics=ArrayAgg(
            "current_config__interface__vlan__fabric__name",
            filter=Q(
                current_config__interface__vlan__fabric__name__isnull=False
            ),
            distinct=True,
        ),
        spaces=ArrayAgg(
            "current_config__interface__vlan__space__name",
            filter=Q(
                current_config__interface__vlan__space__name__isnull=False
            ),
            distinct=True,
        ),
    ).values("fabrics", "spaces")


def _get_extra_macs_qs(machines):
    return (
        machines.filter(
            current_config__interface__type=INTERFACE_TYPE.PHYSICAL,
        )
        .annotate(
            extra_macs=ArrayAgg(
                "current_config__interface__mac_address",
                filter=~Q(
                    current_config__interface__id=F("boot_interface_id")
                ),
                ordering="id",
            )
        )
        .values("extra_macs")
    )


COMBINED_STATUS_MAP = {
    (
        SCRIPT_STATUS.APPLYING_NETCONF,
        SCRIPT_STATUS.INSTALLING,
        SCRIPT_STATUS.RUNNING,
    ): SCRIPT_STATUS.RUNNING,
    (
        SCRIPT_STATUS.FAILED,
        SCRIPT_STATUS.TIMEDOUT,
        SCRIPT_STATUS.FAILED_INSTALLING,
        SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
    ): SCRIPT_STATUS.FAILED,
}

OTHER_COMBINED_STATUSES = (
    SCRIPT_STATUS.APPLYING_NETCONF,
    SCRIPT_STATUS.INSTALLING,
    SCRIPT_STATUS.PENDING,
    SCRIPT_STATUS.ABORTED,
    SCRIPT_STATUS.DEGRADED,
)

TESTS_TYPE_MAP = {
    "cpu": HARDWARE_TYPE.CPU,
    "memory": HARDWARE_TYPE.MEMORY,
    "network": HARDWARE_TYPE.NETWORK,
    "storage": HARDWARE_TYPE.STORAGE,
}


def _get_testing_qs(machines):
    return (
        machines.order_by("id")
        .filter(
            scriptset__result_type=RESULT_TYPE.TESTING,
        )
        .alias(
            result_text_status=EnumValues(
                "scriptset__scriptresult__status",
                TESTING_STATUSES_MAP,
                default=Value("failed"),
            ),
            result_hardware_type=Coalesce(
                F("scriptset__scriptresult__script__hardware_type"),
                Value(HARDWARE_TYPE.NODE),
            ),
            **{
                f"result_combined_{combined_status}_counts": Sum(
                    Case(
                        When(
                            Q(
                                scriptset__scriptresult__suppressed=False,
                                scriptset__scriptresult__status__in=statuses,
                            ),
                            then=Value(1),
                        ),
                        default=Value(0),
                    )
                )
                for statuses, combined_status in COMBINED_STATUS_MAP.items()
            },
        )
        .annotate(
            testing_status=JSONBBuildObject(
                {
                    status: Sum(
                        Case(
                            When(
                                result_text_status=Value(status), then=Value(1)
                            ),
                            default=Value(0),
                        )
                    )
                    for status in TESTING_STATUSES
                }
                | {
                    "status": Case(
                        *(
                            When(
                                Q(
                                    scriptset__scriptresult__suppressed=False,
                                    scriptset__scriptresult__status__in=statuses,
                                ),
                                then=Value(combined_status),
                            )
                            for statuses, combined_status in COMBINED_STATUS_MAP.items()
                        ),
                        *(
                            When(
                                Q(
                                    scriptset__scriptresult__suppressed=False,
                                    scriptset__scriptresult__status=status,
                                ),
                                then=Value(status),
                            )
                            for status in OTHER_COMBINED_STATUSES
                        ),
                        default=Value(-1),
                    ),
                }
            ),
            **{
                f"{test_type}_test_status": JSONBBuildObject(
                    {
                        status: Sum(
                            Case(
                                When(
                                    Q(
                                        result_hardware_type=Value(
                                            hardware_type
                                        ),
                                        result_text_status=Value(status),
                                    ),
                                    then=Value(1),
                                ),
                                default=Value(0),
                            )
                        )
                        for status in TESTING_STATUSES
                    }
                    | {
                        "status": Case(
                            *(
                                When(
                                    Q(
                                        result_hardware_type=Value(
                                            hardware_type
                                        ),
                                        scriptset__scriptresult__suppressed=False,
                                        scriptset__scriptresult__status__in=statuses,
                                    ),
                                    then=Value(combined_status),
                                )
                                for statuses, combined_status in COMBINED_STATUS_MAP.items()
                            ),
                            *(
                                When(
                                    Q(
                                        result_hardware_type=Value(
                                            hardware_type
                                        ),
                                        scriptset__scriptresult__suppressed=False,
                                        scriptset__scriptresult__status=status,
                                    ),
                                    then=Value(status),
                                )
                                for status in OTHER_COMBINED_STATUSES
                            ),
                            default=Value(-1),
                        ),
                    }
                )
                for test_type, hardware_type in TESTS_TYPE_MAP.items()
            },
        )
        .values(
            "testing_status",
            *(f"{test_type}_test_status" for test_type in TESTS_TYPE_MAP),
        )
    )


def _get_ipaddress_data(machine_ids=None):
    staticipaddress = StaticIPAddress.objects
    if machine_ids is not None:
        staticipaddress = staticipaddress.filter(
            interface__node_config__node_id__in=machine_ids,
        )

    ipaddress_entries = (
        staticipaddress.filter(
            alloc_type__in=(
                IPADDRESS_TYPE.DHCP,
                IPADDRESS_TYPE.AUTO,
                IPADDRESS_TYPE.STICKY,
                IPADDRESS_TYPE.USER_RESERVED,
                IPADDRESS_TYPE.DISCOVERED,
            )
        )
        .values_list("interface__node_config__node_id")
        .annotate(
            ips=ArrayAgg(
                "ip", filter=~Q(alloc_type=IPADDRESS_TYPE.DISCOVERED)
            ),
            discovered_ips=ArrayAgg(
                "ip",
                filter=Q(
                    alloc_type=IPADDRESS_TYPE.DISCOVERED, ip__isnull=False
                ),
            ),
            is_boot=Case(
                When(
                    Q(
                        interface=F(
                            "interface__node_config__node__boot_interface"
                        )
                    ),
                    then=Value(True),
                ),
                default=Value(False),
            ),
            has_dhcp=Exists(
                StaticIPAddress.objects.exclude(ip__isnull=True).filter(
                    interface__id=OuterRef("interface__id"),
                    alloc_type=IPADDRESS_TYPE.DHCP,
                )
            ),
        )
    )
    ipaddress_data = {}
    discovered_ipaddress_data = {}
    for (
        node_id,
        ips,
        discovered_ips,
        is_boot,
        has_dhcp,
    ) in ipaddress_entries:
        node_ipaddress_data = ipaddress_data.setdefault(node_id, [])

        include_discovered = False
        for ip in ips:
            if ip:
                node_ipaddress_data.append({"ip": ip, "is_boot": is_boot})
            elif has_dhcp:
                include_discovered = True
        if include_discovered and discovered_ips:
            node_ipaddress_data.append(
                {"ip": discovered_ips[0], "is_boot": is_boot}
            )

        # keep track of all discovered IPs separately
        discovered_ipaddress_data.setdefault(node_id, []).extend(
            {"ip": ip, "is_boot": is_boot} for ip in discovered_ips
        )

    return {
        node_id: ips or discovered_ipaddress_data[node_id]
        for node_id, ips in ipaddress_data.items()
    }
