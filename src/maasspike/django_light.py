from collections.abc import Iterable
from itertools import chain
import logging

from django.contrib.auth.models import User
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db.models import (
    BigIntegerField,
    BooleanField,
    CASCADE,
    Case,
    CharField,
    Count,
    DateTimeField,
    DO_NOTHING,
    Exists,
    FloatField,
    ForeignKey,
    Func,
    GenericIPAddressField,
    IntegerField,
    Manager,
    ManyToManyField,
    Model,
    OuterRef,
    PROTECT,
    Q,
    SET_DEFAULT,
    SET_NULL,
    Subquery,
    Sum,
    TextField,
    When,
)
from django.db.models.expressions import F, Value
from django.db.models.functions import Cast, Coalesce, Concat

from maasserver.enum import (
    INTERFACE_TYPE,
    INTERFACE_TYPE_CHOICES,
    IPADDRESS_TYPE,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
    POWER_STATE,
    POWER_STATE_CHOICES,
    SIMPLIFIED_NODE_STATUS,
    SIMPLIFIED_NODE_STATUSES_MAP,
)
from metadataserver.enum import (
    HARDWARE_TYPE,
    HARDWARE_TYPE_CHOICES,
    RESULT_TYPE,
    RESULT_TYPE_CHOICES,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
    SCRIPT_TYPE_CHOICES,
)


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


class Zone(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_zone"
        managed = False

    name = CharField(max_length=256, unique=True)


class Domain(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_domain"
        managed = False

    name = CharField(max_length=256, unique=True)


class ResourcePool(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_resourcepool"
        managed = False

    name = CharField(max_length=256, unique=True)


class Tag(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_tag"
        managed = False

    name = CharField(max_length=256, unique=True)


class NodeConfig(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_nodeconfig"
        unique_together = ("node", "name")
        managed = False

    name = TextField(default="discovered")
    node = ForeignKey("Node", on_delete=CASCADE)


class NUMANode(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_numanode"
        unique_together = ("node", "index")
        managed = False

    node = ForeignKey("Node", on_delete=CASCADE)
    index = IntegerField(default=0)
    memory = IntegerField()
    cores = ArrayField(IntegerField(), blank=True)


class BlockDevice(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_blockdevice"
        unique_together = ("node_config", "name")
        managed = False

    node_config = ForeignKey("NodeConfig", on_delete=CASCADE)
    name = CharField(max_length=255)
    size = BigIntegerField()
    tags = ArrayField(TextField(), blank=True, null=True, default=list)


class PhysicalBlockDevice(BlockDevice):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_physicalblockdevice"
        managed = False

    numa_node = ForeignKey(
        NUMANode, related_name="blockdevices", on_delete=CASCADE
    )


class Fabric(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_fabric"
        managed = False

    name = CharField(max_length=256, null=True, blank=True)


class Space(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_space"
        managed = False

    name = CharField(max_length=256, null=True, blank=True)


class VLAN(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_vlan"
        unique_together = ("vid", "fabric")
        managed = False

    name = CharField(max_length=256, null=True, blank=True)
    vid = IntegerField()
    fabric = ForeignKey(Fabric, on_delete=CASCADE)
    space = ForeignKey(Space, null=True, on_delete=SET_NULL)


class Subnet(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_subnet"
        managed = False

    name = CharField(max_length=255, blank=False)
    vlan = ForeignKey(VLAN, on_delete=PROTECT)


class StaticIPAddress(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_staticipaddress"
        unique_together = ("alloc_type", "ip")
        managed = False

    alloc_type = IntegerField(default=IPADDRESS_TYPE.AUTO)
    ip = GenericIPAddressField(null=True, blank=True)
    subnet = ForeignKey(Subnet, null=True, on_delete=CASCADE)


class Interface(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_interface"
        unique_together = ("node_config", "name")
        managed = False

    node_config = ForeignKey(NodeConfig, null=True, on_delete=CASCADE)
    name = CharField(max_length=255)
    # don't need a MACAddressField here since it's only for reading
    mac_address = TextField(unique=False, null=True, blank=True)
    type = CharField(max_length=20, choices=INTERFACE_TYPE_CHOICES)
    vlan = ForeignKey(VLAN, null=True, on_delete=PROTECT)
    ip_addresses = ManyToManyField("StaticIPAddress")


class BMC(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_bmc"
        managed = False

    power_type = CharField(max_length=10, blank=True)


class EventType(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_eventtype"
        managed = False

    name = CharField(max_length=255, unique=True)
    description = CharField(max_length=255)
    level = IntegerField()


class Event(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_event"
        managed = False

    type = ForeignKey(EventType, on_delete=PROTECT)
    node = ForeignKey("Node", null=True, on_delete=DO_NOTHING)
    created = DateTimeField()
    description = TextField(blank=True, default="")


class MachineManager(Manager):
    def get_queryset(self):
        return super().get_queryset().filter(node_type=NODE_TYPE.MACHINE)


class Node(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_node"
        managed = False

    machines = MachineManager()

    architecture = CharField(max_length=31, blank=True, null=True)
    bmc = ForeignKey(BMC, null=True, on_delete=CASCADE)
    boot_interface = ForeignKey(
        Interface, null=True, related_name="+", on_delete=SET_NULL
    )
    cpu_count = IntegerField(default=0)
    current_config = ForeignKey(
        NodeConfig, null=True, on_delete=CASCADE, related_name="+"
    )
    description = TextField(blank=True, default="")
    distro_series = CharField(max_length=255, blank=True, default="")
    domain = ForeignKey(Domain, null=True, on_delete=PROTECT)
    error_description = TextField(blank=True, default="")
    hostname = CharField(max_length=255, default="", blank=True, unique=True)
    locked = BooleanField(default=False)
    memory = IntegerField(default=0)
    node_type = IntegerField(
        choices=NODE_TYPE_CHOICES, default=NODE_TYPE.DEFAULT
    )
    osystem = CharField(max_length=255, blank=True, default="")
    owner = ForeignKey(User, null=True, on_delete=PROTECT)
    parent = ForeignKey(
        "Node", null=True, related_name="children", on_delete=CASCADE
    )
    pool = ForeignKey(ResourcePool, null=True, on_delete=PROTECT)
    power_state = CharField(
        max_length=10,
        choices=POWER_STATE_CHOICES,
        default=POWER_STATE.UNKNOWN,
    )
    status = IntegerField(choices=NODE_STATUS_CHOICES)
    system_id = CharField(
        max_length=41,
        unique=True,
    )
    tags = ManyToManyField(Tag)
    zone = ForeignKey(Zone, on_delete=SET_DEFAULT)


class OwnerData(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "maasserver_ownerdata"
        managed = False
        unique_together = ("node", "key")

    node = ForeignKey(Node, on_delete=CASCADE)
    key = CharField(max_length=255)
    value = TextField()


class Script(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "metadataserver_script"
        managed = False

    name = CharField(max_length=255, unique=True)
    script_type = IntegerField(choices=SCRIPT_TYPE_CHOICES)
    hardware_type = IntegerField(choices=HARDWARE_TYPE_CHOICES)


class ScriptSet(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "metadataserver_scriptset"
        managed = False

    node = ForeignKey(Node, on_delete=CASCADE)
    result_type = IntegerField(choices=RESULT_TYPE_CHOICES)


class ScriptResult(Model):
    class Meta:
        app_label = "maasspike"
        db_table = "metadataserver_scriptresult"
        managed = False

    script_set = ForeignKey(ScriptSet, on_delete=CASCADE)
    script = ForeignKey(Script, null=True, on_delete=CASCADE)
    status = IntegerField(choices=SCRIPT_STATUS_CHOICES)
    suppressed = BooleanField(default=False)
    physical_blockdevice = ForeignKey(
        PhysicalBlockDevice,
        null=True,
        on_delete=CASCADE,
    )
    interface = ForeignKey(Interface, null=True, on_delete=CASCADE)


TESTING_STATUSES_MAP = {
    SCRIPT_STATUS.PENDING: "pending",
    SCRIPT_STATUS.RUNNING: "running",
    (SCRIPT_STATUS.PASSED, SCRIPT_STATUS.SKIPPED): "passed",
}

TESTING_STATUSES = list(TESTING_STATUSES_MAP.values()) + ["failed"]


def list_machines(admin, limit=None):
    machines_qs = Node.machines.order_by("id")
    if limit is None:
        machine_ids = None
    else:
        machine_ids = list(machines_qs.values_list("id", flat=True)[:limit])
        machines_qs = machines_qs.filter(id__in=machine_ids)

    entries = _get_machines_qs(machines_qs, admin.is_superuser)
    storage_entries = _get_storage_qs(machines_qs)
    network_entries = _get_network_qs(machines_qs)
    testing_entries = _get_testing_qs(machines_qs)

    boot_interfaces, interfaces_data = _get_interfaces_data(machine_ids)
    vlan_data = _get_vlan_data(boot_interfaces)
    ipaddress_data = _get_ipaddress_data(
        boot_interfaces, machine_ids=machine_ids
    )

    result = []
    # entries match in both querysets because of ordering by ID and containing
    # all results
    all_entries = zip(
        entries, storage_entries, network_entries, testing_entries
    )
    for entry, storage_entry, network_entry, testing_entry in all_entries:
        entry |= storage_entry | network_entry | testing_entry

        # computed fields
        node_id = entry["id"]
        entry.update(interfaces_data[node_id])
        entry["vlan"] = vlan_data.get(node_id)
        entry["ip_addresses"] = ipaddress_data.get(node_id, [])

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
        fqdn=Concat(F("hostname"), Value("."), F("domain__name")),
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


def _get_interfaces_data(machine_ids=None):
    interfaces = Interface.objects.order_by("node_config__node_id", "name")
    if machine_ids is None:
        interfaces = interfaces.filter(
            node_config__node__node_type=NODE_TYPE.MACHINE
        )
    else:
        interfaces = interfaces.filter(node_config__node_id__in=machine_ids)

    interface_id_to_mac = dict(interfaces.values_list("id", "mac_address"))

    node_interface_entries = (
        Node.machines.filter(
            current_config__interface__type=INTERFACE_TYPE.PHYSICAL,
        )
        .values_list("id", "boot_interface_id")
        .annotate(
            all_interfaces=ArrayAgg(
                "current_config__interface__id",
                ordering="current_config__interface__id",
            ),
        )
    )
    if machine_ids is not None:
        node_interface_entries = node_interface_entries.filter(
            id__in=machine_ids
        )

    # map boot interface ID to machine ID
    boot_interfaces = {}
    interfaces_data = {}
    for node_id, boot_if_id, node_if_ids in node_interface_entries:
        if boot_if_id is None:
            boot_if_id = node_if_ids.pop(0)
        else:
            node_if_ids.remove(boot_if_id)
        boot_interfaces[boot_if_id] = node_id
        interfaces_data[node_id] = {
            "pxe_mac": interface_id_to_mac[boot_if_id],
            "extra_macs": [
                interface_id_to_mac[if_id] for if_id in node_if_ids
            ],
        }
    return boot_interfaces, interfaces_data


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


def _get_vlan_data(boot_interfaces):
    vlan_entries = (
        VLAN.objects.filter(interface__in=boot_interfaces)
        .values("id", "fabric_id", "interface__id")
        .annotate(
            fabric_name=Coalesce(
                "fabric__name",
                Concat(Value("fabric-"), F("id"), output_field=CharField()),
            ),
            name=Coalesce("name", Value("None")),
        )
    )
    return {
        boot_interfaces[entry.pop("interface__id")]: entry
        for entry in vlan_entries
    }


def _get_ipaddress_data(boot_interfaces, machine_ids=None):
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
        .values_list("interface__node_config__node_id", "interface__id")
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
        interface_id,
        ips,
        discovered_ips,
        has_dhcp,
    ) in ipaddress_entries:
        node_ipaddress_data = ipaddress_data.setdefault(node_id, [])
        is_boot = interface_id in boot_interfaces

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
