from collections.abc import Iterable
import logging

from django.contrib.auth.models import User
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
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
    (SCRIPT_STATUS.ABORTED, SCRIPT_STATUS.DEGRADED): "",  # skipped in status
}


def testing_status_dict(global_status=None):
    status = dict.fromkeys(("pending", "running", "passed", "failed"), 0)
    status["status"] = global_status
    return status


def list_machines(admin, limit=None):
    user_permissions = ["edit", "delete"] if admin.is_superuser else []

    machines = Node.machines.order_by("id")
    if limit is None:
        machine_ids = None
    else:
        machine_ids = list(machines.values_list("id", flat=True)[:limit])
        machines = machines.filter(id__in=machine_ids)

    entries = machines.values(
        "architecture",
        "cpu_count",
        "description",
        "distro_series",
        "domain__id",
        "domain__name",
        "error_description",
        "hostname",
        "id",
        "locked",
        "osystem",
        "pool__id",
        "pool__name",
        "power_state",
        "system_id",
        "zone__id",
        "zone__name",
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
    )

    storage_data = _get_storage_data(machine_ids=machine_ids)
    boot_interfaces, interfaces_data = _get_interfaces_data(machine_ids)
    networks_data = _get_networks_data(machine_ids=machine_ids)
    testing_data = _get_testing_data(machine_ids=machine_ids)
    vlan_data = _get_vlan_data(boot_interfaces)
    ipaddress_data = _get_ipaddress_data(
        boot_interfaces, machine_ids=machine_ids
    )

    result = []
    for entry in entries:
        node_id = entry["id"]
        # extend existing dict from storage data, as it's not used elsewhere
        new_entry = storage_data[node_id]

        sub_entries = {}
        for key, value in entry.items():
            if "__" in key:
                item, subkey = key.split("__")
                sub_entries.setdefault(item, {})[subkey] = value
            else:
                new_entry[key] = value
        new_entry.update(sub_entries)

        # computed fields
        new_entry.update(networks_data[node_id])
        new_entry.update(interfaces_data[node_id])
        new_entry["permissions"] = (
            [] if new_entry["locked"] else user_permissions
        )
        new_entry["vlan"] = vlan_data.get(node_id)
        new_entry["ip_addresses"] = ipaddress_data.get(node_id, [])

        testing_statuses = testing_data.get(node_id, {})

        def add_status(key, hardware_type):
            new_entry[key] = testing_statuses.get(
                hardware_type, testing_status_dict(global_status=-1)
            )

        add_status("cpu_test_status", HARDWARE_TYPE.CPU)
        add_status("memory_test_status", HARDWARE_TYPE.MEMORY)
        add_status("network_test_status", HARDWARE_TYPE.NETWORK)
        add_status("storage_test_status", HARDWARE_TYPE.STORAGE)
        add_status("testing_status", None)
        result.append(new_entry)
    return result


def _get_storage_data(machine_ids):
    entries = Node.machines.values_list("id").annotate(
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
    )
    if machine_ids is not None:
        entries = entries.filter(id__in=machine_ids)
    return {
        node_id: {
            "physical_disk_count": physical_disk_count,
            "storage": storage,
        }
        for node_id, physical_disk_count, storage in entries
    }


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


def _get_networks_data(machine_ids=None):
    network_entries = Node.machines.values_list("id").annotate(
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
    )
    if machine_ids is not None:
        network_entries = network_entries.filter(id__in=machine_ids)
    return {
        node_id: {"fabrics": fabrics, "spaces": spaces}
        for node_id, fabrics, spaces in network_entries
    }


ORDERING_STATUS_MAP = {
    status: index
    for index, status in enumerate(
        (
            SCRIPT_STATUS.RUNNING,
            SCRIPT_STATUS.APPLYING_NETCONF,
            SCRIPT_STATUS.INSTALLING,
            SCRIPT_STATUS.PENDING,
            SCRIPT_STATUS.ABORTED,
            SCRIPT_STATUS.FAILED,
            SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
            SCRIPT_STATUS.FAILED_INSTALLING,
            SCRIPT_STATUS.TIMEDOUT,
            SCRIPT_STATUS.DEGRADED,
        )
    )
}

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


def _get_testing_data(machine_ids):
    testing_entries = (
        ScriptResult.objects.order_by("-id")
        .filter(
            script_set__result_type=RESULT_TYPE.TESTING,
        )
        .values("id", "suppressed")
        .annotate(
            text_status=EnumValues(
                "status", TESTING_STATUSES_MAP, default=Value("failed")
            ),
            combined_status=EnumValues(
                "status",
                COMBINED_STATUS_MAP,
                default=F("status"),
                output_field=IntegerField(),
            ),
            node_id=F("script_set__node_id"),
            hardware_type=Coalesce(
                F("script__hardware_type"), Value(HARDWARE_TYPE.NODE)
            ),
        )
        .order_by(EnumValues("status", ORDERING_STATUS_MAP))
    )
    if machine_ids is not None:
        testing_entries = testing_entries.filter(
            script_set__node_id__in=machine_ids
        )

    testing_data = {}
    for entry in testing_entries:
        status_data = testing_data.setdefault(entry["node_id"], {}).setdefault(
            entry["hardware_type"], testing_status_dict()
        )
        # null key for global status
        global_status_data = testing_data.setdefault(
            entry["node_id"], {}
        ).setdefault(None, testing_status_dict())
        status = entry["text_status"]
        if status:
            status_data[status] += 1
            global_status_data[status] += 1
        # take the combined status from the first entry since they're sorted by
        # status priority
        if not entry["suppressed"]:
            if status_data["status"] is None:
                status_data["status"] = entry["combined_status"]
            if global_status_data["status"] is None:
                global_status_data["status"] = entry["combined_status"]
    return testing_data


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
