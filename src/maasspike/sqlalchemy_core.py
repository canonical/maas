import logging

from sqlalchemy import (
    Boolean,
    case,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    select,
    String,
    Table,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.expression import func

from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    SIMPLIFIED_NODE_STATUS,
    SIMPLIFIED_NODE_STATUSES_MAP_REVERSED,
)
from metadataserver.enum import HARDWARE_TYPE, RESULT_TYPE, SCRIPT_STATUS

# Copied from maasserver.websocket.handlers.node
NODE_TYPE_TO_LINK_TYPE = {
    NODE_TYPE.DEVICE: "device",
    NODE_TYPE.MACHINE: "machine",
    NODE_TYPE.RACK_CONTROLLER: "controller",
    NODE_TYPE.REGION_CONTROLLER: "controller",
    NODE_TYPE.REGION_AND_RACK_CONTROLLER: "controller",
}


metadata_obj = MetaData()


Machine = Table(
    "maasserver_node",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("system_id", String),
    Column("hostname", String),
    Column("architecture", String),
    Column("distro_series", String),
    Column("osystem", String),
    Column("status", Integer),
    Column("node_type", Integer),
    Column("cpu_count", Integer),
    Column("memory", Integer),
    Column("description", String),
    Column("error_description", String),
    Column("power_state", String),
    Column("locked", Boolean),
    Column("domain_id", ForeignKey("maasserver_domain.id")),
    Column("owner_id", ForeignKey("auth_user.id")),
    Column("parent_id", ForeignKey("maasserver_node.id")),
    Column("pool_id", ForeignKey("maasserver_resourcepool.id")),
    Column("zone_id", ForeignKey("maasserver_zone.id")),
    Column("current_config_id", ForeignKey("maasserver_nodeconfig.id")),
    Column("boot_interface_id", ForeignKey("maasserver_interface.id")),
    Column("bmc_id", ForeignKey("maasserver_bmc.id")),
)


Event = Table(
    "maasserver_event",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("created", DateTime(timezone=True)),
    Column("description", String),
    Column("type_id", ForeignKey("maasserver_eventtype.id")),
    Column("node_id", ForeignKey("maasserver_node.id")),
)


EventType = Table(
    "maasserver_eventtype",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("description", String),
    Column("level", Integer),
)


BMC = Table(
    "maasserver_bmc",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("power_type", String),
)


Domain = Table(
    "maasserver_domain",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String),
)


User = Table(
    "auth_user",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("username", String),
)


ResourcePool = Table(
    "maasserver_resourcepool",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String),
)


Zone = Table(
    "maasserver_zone",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String),
)


Tag = Table(
    "maasserver_tag",
    metadata_obj,
    Column("id", Integer, primary_key=True),
)


NodeTag = Table(
    "maasserver_node_tags",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("node_id", ForeignKey("Machine.id")),
    Column("tag_id", ForeignKey("Tag.id")),
)


NodeConfig = Table(
    "maasserver_nodeconfig",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("node_id", ForeignKey("Machine.id")),
)


Fabric = Table(
    "maasserver_fabric",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String),
)


Space = Table(
    "maasserver_space",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String),
)


Vlan = Table(
    "maasserver_vlan",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("fabric_id", ForeignKey("Fabric.id")),
    Column("space_id", ForeignKey("Space.id")),
)


Interface = Table(
    "maasserver_interface",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("type", Integer),
    Column("node_config_id", ForeignKey("NodeConfig.id")),
    Column("vlan_id", ForeignKey("Vlan.id")),
    Column("mac_address", String),
)

StaticIPAddress = Table(
    "maasserver_staticipaddress",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("ip", postgresql.INET),
    Column("alloc_type", Integer),
)


InterfaceIPAddresses = Table(
    "maasserver_interface_ip_addresses",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("interface_id", ForeignKey("maasserver_interface.id")),
    Column("staticipaddress_id", ForeignKey("maasserver_staticipaddress.id")),
)


BlockDevice = Table(
    "maasserver_blockdevice",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("size", Integer),
    Column("node_config_id", ForeignKey("NodeConfig.id")),
    Column("tags", postgresql.ARRAY(String)),
)


PhysicalBlockDevice = Table(
    "maasserver_physicalblockdevice",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String),
    Column("blockdevice_ptr_id", ForeignKey("BlockDevice.id")),
)


PartitionTable = Table(
    "maasserver_partitiontable",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("block_device_id", ForeignKey("BlockDevice.id")),
)


Partition = Table(
    "maasserver_partition",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("partition_table_id", ForeignKey("PartitionTable.id")),
    Column("tags", postgresql.ARRAY(String)),
)


ScriptSet = Table(
    "metadataserver_scriptset",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("node_id", ForeignKey("maasserver_node.id")),
    Column("result_type", Integer),
)


ScriptResult = Table(
    "metadataserver_scriptresult",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("script_set_id", ForeignKey("metadataserver_scriptset.id")),
    Column("script_id", ForeignKey("metadataserver_script.id")),
    Column("status", Integer),
    Column("suppressed", Boolean),
)


Script = Table(
    "metadataserver_script",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("hardware_type", Integer),
)


PLAIN_LIST_ATTRIBUTES = [
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
]


def list_machines_one_query(conn, admin, limit=None):
    """Use SQLAlchemy core to get the data in one query.

    This handler should always use one query only, to show how well the data
    model works for this.

    If the query needs to be split to be quicker, do so in another handler.
    """
    query = get_single_query(limit=limit)
    rows = list(conn.execute(query))
    return get_machines(rows, admin)


def get_single_query(limit=None):
    storage_query = (
        select(
            Machine.c.id,
            func.count(PhysicalBlockDevice.c.blockdevice_ptr_id).label(
                "disk_count"
            ),
            func.sum(func.coalesce(BlockDevice.c.size, 0)).label("storage"),
        )
        .select_from(PhysicalBlockDevice)
        .join(
            BlockDevice,
            BlockDevice.c.id == PhysicalBlockDevice.c.blockdevice_ptr_id,
        )
        .join(NodeConfig, NodeConfig.c.id == BlockDevice.c.node_config_id)
        .join(Machine, Machine.c.id == NodeConfig.c.node_id)
        .group_by(Machine.c.id)
    ).cte("storage")
    interfaces_cte = (
        select(
            Machine.c.id.label("machine_id"),
            Interface.c.id.label("interface_id"),
        )
        .select_from(Interface)
        .join(NodeConfig, NodeConfig.c.id == Interface.c.node_config_id)
        .join(Machine, Machine.c.current_config_id == NodeConfig.c.id)
    ).cte("interfaces")
    vlans_cte = (
        select(
            Vlan.c.id,
            Machine.c.id.label("machine_id"),
        )
        .join(Interface, Interface.c.vlan_id == Vlan.c.id)
        .join(NodeConfig, NodeConfig.c.id == Interface.c.node_config_id)
        .join(Machine, Machine.c.current_config_id == NodeConfig.c.id)
    ).cte("vlans")
    fabrics_cte = (
        select(
            vlans_cte.c.machine_id,
            postgresql.array_agg(func.distinct(Fabric.c.name)).label("names"),
        )
        .select_from(Fabric)
        .join(Vlan, Vlan.c.fabric_id == Fabric.c.id)
        .join(vlans_cte, vlans_cte.c.id == Vlan.c.id)
        .group_by(vlans_cte.c.machine_id)
    ).cte("fabrics")
    spaces_cte = (
        select(
            vlans_cte.c.machine_id,
            postgresql.array_agg(func.distinct(Space.c.name)).label("names"),
        )
        .select_from(Space)
        .join(Vlan, Vlan.c.space_id == Space.c.id)
        .join(vlans_cte, vlans_cte.c.id == Vlan.c.id)
        .group_by(vlans_cte.c.machine_id)
    ).cte("spaces")
    boot_interface_cte = (
        select(
            Machine.c.id,
            func.coalesce(Machine.c.boot_interface_id, Interface.c.id).label(
                "boot_interface_id"
            ),
        )
        .select_from(Machine)
        .distinct(Machine.c.id)
        .join(NodeConfig, NodeConfig.c.id == Machine.c.current_config_id)
        .join(Interface, Interface.c.node_config_id == NodeConfig.c.id)
        .where(
            Interface.c.type == INTERFACE_TYPE.PHYSICAL,
        )
        .order_by(Machine.c.id, Interface.c.id.asc())
    ).cte("boot_interface_cte")
    extra_macs_cte = (
        select(
            Machine.c.id,
            postgresql.array_agg(Interface.c.mac_address).label("extra_macs"),
        )
        .join(NodeConfig, NodeConfig.c.id == Machine.c.current_config_id)
        .join(Interface, Interface.c.node_config_id == NodeConfig.c.id)
        .join(boot_interface_cte, boot_interface_cte.c.id == Machine.c.id)
        .where(
            Interface.c.id != boot_interface_cte.c.boot_interface_id,
            Interface.c.type == INTERFACE_TYPE.PHYSICAL,
        )
        .group_by(Machine.c.id)
    ).cte("extra_macs")
    status_message_subquery = (
        select(
            func.concat(
                EventType.c.description,
                " - ",
                Event.c.description,
            ).label("status_message"),
        )
        .select_from(Event)
        .join(EventType, EventType.c.id == Event.c.type_id)
        .order_by(Event.c.node_id, Event.c.created.desc(), Event.c.id.desc())
        .where(
            Machine.c.id == Event.c.node_id,
            EventType.c.level >= logging.INFO,
        )
        .limit(1)
    ).scalar_subquery()
    discovered_addresses_cte = (
        select(
            Interface.c.id,
            StaticIPAddress.c.ip,
        )
        .select_from(Interface)
        .join(
            InterfaceIPAddresses,
            Interface.c.id == InterfaceIPAddresses.c.interface_id,
        )
        .join(
            StaticIPAddress,
            InterfaceIPAddresses.c.staticipaddress_id == StaticIPAddress.c.id,
        )
        .where(
            StaticIPAddress.c.alloc_type == IPADDRESS_TYPE.DISCOVERED,
            StaticIPAddress.c.ip.is_not(None),
        )
    ).cte("discovered_addresses")

    DiscoveredAddress = StaticIPAddress.alias("discovered_ip")
    DiscoveredInterfaceIPAddresses = InterfaceIPAddresses.alias(
        "discovered_interface_ip"
    )
    dhcp_address_cte = (
        select(
            StaticIPAddress.c.id,
            DiscoveredAddress.c.ip,
        )
        .select_from(StaticIPAddress)
        .distinct(StaticIPAddress.c.id)
        .join(
            InterfaceIPAddresses,
            InterfaceIPAddresses.c.staticipaddress_id == StaticIPAddress.c.id,
        )
        .join(
            DiscoveredInterfaceIPAddresses,
            DiscoveredInterfaceIPAddresses.c.interface_id
            == InterfaceIPAddresses.c.interface_id,
        )
        .join(
            DiscoveredAddress,
            DiscoveredAddress.c.id
            == InterfaceIPAddresses.c.staticipaddress_id,
        )
        .where(
            StaticIPAddress.c.alloc_type == IPADDRESS_TYPE.DHCP,
            DiscoveredAddress.c.alloc_type == IPADDRESS_TYPE.DISCOVERED,
            DiscoveredAddress.c.ip.is_not(None),
        )
        .order_by(StaticIPAddress.c.id, DiscoveredAddress.c.id.desc())
    ).cte("dhcp_address")
    interface_addresses_cte = (
        select(
            Interface.c.id,
            case(
                (
                    StaticIPAddress.c.alloc_type == IPADDRESS_TYPE.DHCP,
                    dhcp_address_cte.c.ip,
                ),
                else_=StaticIPAddress.c.ip,
            ).label("ip"),
        )
        .select_from(Interface)
        .join(
            InterfaceIPAddresses,
            Interface.c.id == InterfaceIPAddresses.c.interface_id,
        )
        .join(
            StaticIPAddress,
            InterfaceIPAddresses.c.staticipaddress_id == StaticIPAddress.c.id,
        )
        .join(
            dhcp_address_cte,
            dhcp_address_cte.c.id == StaticIPAddress.c.id,
            isouter=True,
        )
    ).cte("interface_addresses")
    ip_addresses_cte = (
        select(
            Machine.c.id,
            postgresql.array_agg(interface_addresses_cte.c.ip).label("ips"),
            postgresql.array_agg(
                interface_addresses_cte.c.id
                == boot_interface_cte.c.boot_interface_id
            ).label("is_boot_ips"),
        )
        .select_from(Machine)
        .join(interfaces_cte, interfaces_cte.c.machine_id == Machine.c.id)
        .join(
            interface_addresses_cte,
            interface_addresses_cte.c.id == interfaces_cte.c.interface_id,
        )
        .join(boot_interface_cte, boot_interface_cte.c.id == Machine.c.id)
        .group_by(Machine.c.id)
    ).cte("ip_addresses")
    discovered_machine_addresses_cte = (
        select(
            Machine.c.id,
            postgresql.array_agg(discovered_addresses_cte.c.ip).label("ips"),
            postgresql.array_agg(
                discovered_addresses_cte.c.id
                == boot_interface_cte.c.boot_interface_id
            ).label("is_boot_ips"),
        )
        .select_from(Machine)
        .join(interfaces_cte, interfaces_cte.c.machine_id == Machine.c.id)
        .join(
            discovered_addresses_cte,
            discovered_addresses_cte.c.id == interfaces_cte.c.interface_id,
        )
        .join(boot_interface_cte, boot_interface_cte.c.id == Machine.c.id)
        .group_by(Machine.c.id)
    ).cte("discovered_machine_ip_addresses")
    testing_status_cte = (
        select(
            Machine.c.id,
            func.sum(
                case(
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("testing_status_pending"),
            func.sum(
                case(
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    else_=0,
                ),
            ).label("testing_status_running"),
            func.sum(
                case(
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("testing_status_passed"),
            func.sum(
                case(
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("testing_status_failed"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.APPLYING_NETCONF,
                        1,
                    ),
                    (ScriptResult.c.status == SCRIPT_STATUS.INSTALLING, 1),
                    else_=0,
                ),
            ).label("testing_status_combined_running"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("testing_status_combined_failed"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("testing_status_combined_pending"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    else_=0,
                ),
            ).label("testing_status_combined_aborted"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.DEGRADED, 1),
                    else_=0,
                ),
            ).label("testing_status_combined_degraded"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("testing_status_combined_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("storage_test_status_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    else_=0,
                ),
            ).label("storage_test_status_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("storage_test_status_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("storage_test_status_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.APPLYING_NETCONF,
                        1,
                    ),
                    (ScriptResult.c.status == SCRIPT_STATUS.INSTALLING, 1),
                    else_=0,
                ),
            ).label("storage_test_status_combined_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("storage_test_status_combined_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("storage_test_status_combined_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    else_=0,
                ),
            ).label("storage_test_status_combined_aborted"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.DEGRADED, 1),
                    else_=0,
                ),
            ).label("storage_test_status_combined_degraded"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("storage_test_status_combined_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("network_test_status_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    else_=0,
                ),
            ).label("network_test_status_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("network_test_status_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("network_test_status_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.APPLYING_NETCONF,
                        1,
                    ),
                    (ScriptResult.c.status == SCRIPT_STATUS.INSTALLING, 1),
                    else_=0,
                ),
            ).label("network_test_status_combined_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("network_test_status_combined_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("network_test_status_combined_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    else_=0,
                ),
            ).label("network_test_status_combined_aborted"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.DEGRADED, 1),
                    else_=0,
                ),
            ).label("network_test_status_combined_degraded"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("network_test_status_combined_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("memory_test_status_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    else_=0,
                ),
            ).label("memory_test_status_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("memory_test_status_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("memory_test_status_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.APPLYING_NETCONF,
                        1,
                    ),
                    (ScriptResult.c.status == SCRIPT_STATUS.INSTALLING, 1),
                    else_=0,
                ),
            ).label("memory_test_status_combined_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("memory_test_status_combined_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("memory_test_status_combined_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    else_=0,
                ),
            ).label("memory_test_status_combined_aborted"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.DEGRADED, 1),
                    else_=0,
                ),
            ).label("memory_test_status_combined_degraded"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("memory_test_status_combined_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("cpu_test_status_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.APPLYING_NETCONF,
                        1,
                    ),
                    (ScriptResult.c.status == SCRIPT_STATUS.INSTALLING, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_aborted"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.DEGRADED, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_degraded"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_passed"),
        )
        .select_from(Machine)
        .join(ScriptSet, ScriptSet.c.node_id == Machine.c.id)
        .join(ScriptResult, ScriptResult.c.script_set_id == ScriptSet.c.id)
        .join(Script, Script.c.id == ScriptResult.c.script_id)
        .where(ScriptSet.c.result_type == RESULT_TYPE.TESTING)
        .group_by(Machine.c.id)
    ).cte("testing_status")
    tags_cte = (
        select(
            Machine.c.id,
            postgresql.array_agg(NodeTag.c.tag_id).label("tag_ids"),
        )
        .select_from(Machine)
        .join(NodeTag, NodeTag.c.node_id == Machine.c.id)
        .group_by(Machine.c.id)
    ).cte("machine_tags")
    MachineParent = Machine.alias("parent")
    BootInterface = Interface.alias("boot_interface")
    BootVlan = Vlan.alias("boot_vlan")
    BootFabric = Fabric.alias("boot_fabric")
    stmt = (
        select(
            *[getattr(Machine.c, attr) for attr in PLAIN_LIST_ATTRIBUTES],
            Machine.c.domain_id,
            Machine.c.node_type,
            Machine.c.pool_id,
            Machine.c.status.label("status_code"),
            Machine.c.zone_id,
            Domain.c.name.label("domain_name"),
            func.coalesce(User.c.username, "").label("owner_name"),
            MachineParent.c.system_id.label("parent"),
            ResourcePool.c.name.label("pool_name"),
            Zone.c.name.label("zone_name"),
            storage_query.c.disk_count,
            func.round((storage_query.c.storage / (1000**3)), 1).label(
                "storage"
            ),
            func.round((Machine.c.memory / 1024), 1).label("memory"),
            fabrics_cte.c.names.label("fabrics"),
            func.coalesce(spaces_cte.c.names, []).label("spaces"),
            extra_macs_cte.c.extra_macs,
            BootInterface.c.mac_address.label("pxe_mac"),
            BMC.c.power_type,
            status_message_subquery.label("status_message"),
            BootVlan.c.id.label("boot_vlan_id"),
            BootVlan.c.name.label("boot_vlan_name"),
            BootVlan.c.fabric_id.label("boot_fabric_id"),
            BootFabric.c.name.label("boot_fabric_name"),
            case(
                (
                    ip_addresses_cte.c.ips.is_(None),
                    discovered_machine_addresses_cte.c.ips,
                ),
                else_=ip_addresses_cte.c.ips,
            ).label("ips"),
            case(
                (
                    ip_addresses_cte.c.ips.is_(None),
                    discovered_machine_addresses_cte.c.is_boot_ips,
                ),
                else_=ip_addresses_cte.c.is_boot_ips,
            ).label("is_boot_ips"),
            testing_status_cte.c.testing_status_pending,
            testing_status_cte.c.testing_status_running,
            testing_status_cte.c.testing_status_passed,
            testing_status_cte.c.testing_status_failed,
            case(
                (
                    testing_status_cte.c.testing_status_combined_running > 0,
                    SCRIPT_STATUS.RUNNING,
                ),
                (
                    testing_status_cte.c.testing_status_combined_failed > 0,
                    SCRIPT_STATUS.FAILED,
                ),
                (
                    testing_status_cte.c.testing_status_combined_pending > 0,
                    SCRIPT_STATUS.PENDING,
                ),
                (
                    testing_status_cte.c.testing_status_combined_degraded > 0,
                    SCRIPT_STATUS.DEGRADED,
                ),
                (
                    testing_status_cte.c.testing_status_combined_passed > 0,
                    SCRIPT_STATUS.PASSED,
                ),
                else_=-1,
            ).label("testing_status_combined"),
            testing_status_cte.c.storage_test_status_pending,
            testing_status_cte.c.storage_test_status_running,
            testing_status_cte.c.storage_test_status_passed,
            testing_status_cte.c.storage_test_status_failed,
            case(
                (
                    testing_status_cte.c.storage_test_status_combined_running
                    > 0,
                    SCRIPT_STATUS.RUNNING,
                ),
                (
                    testing_status_cte.c.storage_test_status_combined_failed
                    > 0,
                    SCRIPT_STATUS.FAILED,
                ),
                (
                    testing_status_cte.c.storage_test_status_combined_pending
                    > 0,
                    SCRIPT_STATUS.PENDING,
                ),
                (
                    testing_status_cte.c.storage_test_status_combined_degraded
                    > 0,
                    SCRIPT_STATUS.DEGRADED,
                ),
                (
                    testing_status_cte.c.storage_test_status_combined_passed
                    > 0,
                    SCRIPT_STATUS.PASSED,
                ),
                else_=-1,
            ).label("storage_test_status_combined"),
            testing_status_cte.c.network_test_status_pending,
            testing_status_cte.c.network_test_status_running,
            testing_status_cte.c.network_test_status_passed,
            testing_status_cte.c.network_test_status_failed,
            case(
                (
                    testing_status_cte.c.network_test_status_combined_running
                    > 0,
                    SCRIPT_STATUS.RUNNING,
                ),
                (
                    testing_status_cte.c.network_test_status_combined_failed
                    > 0,
                    SCRIPT_STATUS.FAILED,
                ),
                (
                    testing_status_cte.c.network_test_status_combined_pending
                    > 0,
                    SCRIPT_STATUS.PENDING,
                ),
                (
                    testing_status_cte.c.network_test_status_combined_degraded
                    > 0,
                    SCRIPT_STATUS.DEGRADED,
                ),
                (
                    testing_status_cte.c.network_test_status_combined_passed
                    > 0,
                    SCRIPT_STATUS.PASSED,
                ),
                else_=-1,
            ).label("network_test_status_combined"),
            testing_status_cte.c.cpu_test_status_pending,
            testing_status_cte.c.cpu_test_status_running,
            testing_status_cte.c.cpu_test_status_passed,
            testing_status_cte.c.cpu_test_status_failed,
            case(
                (
                    testing_status_cte.c.cpu_test_status_combined_running > 0,
                    SCRIPT_STATUS.RUNNING,
                ),
                (
                    testing_status_cte.c.cpu_test_status_combined_failed > 0,
                    SCRIPT_STATUS.FAILED,
                ),
                (
                    testing_status_cte.c.cpu_test_status_combined_pending > 0,
                    SCRIPT_STATUS.PENDING,
                ),
                (
                    testing_status_cte.c.cpu_test_status_combined_degraded > 0,
                    SCRIPT_STATUS.DEGRADED,
                ),
                (
                    testing_status_cte.c.cpu_test_status_combined_passed > 0,
                    SCRIPT_STATUS.PASSED,
                ),
                else_=-1,
            ).label("cpu_test_status_combined"),
            testing_status_cte.c.memory_test_status_pending,
            testing_status_cte.c.memory_test_status_running,
            testing_status_cte.c.memory_test_status_passed,
            testing_status_cte.c.memory_test_status_failed,
            case(
                (
                    testing_status_cte.c.memory_test_status_combined_running
                    > 0,
                    SCRIPT_STATUS.RUNNING,
                ),
                (
                    testing_status_cte.c.memory_test_status_combined_failed
                    > 0,
                    SCRIPT_STATUS.FAILED,
                ),
                (
                    testing_status_cte.c.memory_test_status_combined_pending
                    > 0,
                    SCRIPT_STATUS.PENDING,
                ),
                (
                    testing_status_cte.c.memory_test_status_combined_degraded
                    > 0,
                    SCRIPT_STATUS.DEGRADED,
                ),
                (
                    testing_status_cte.c.memory_test_status_combined_passed
                    > 0,
                    SCRIPT_STATUS.PASSED,
                ),
                else_=-1,
            ).label("memory_test_status_combined"),
            tags_cte.c.tag_ids,
        )
        .select_from(Machine)
        .join(Domain, Domain.c.id == Machine.c.domain_id)
        .join(User, isouter=True)
        .join(
            ResourcePool, ResourcePool.c.id == Machine.c.pool_id, isouter=True
        )
        .join(Zone, Zone.c.id == Machine.c.zone_id, isouter=True)
        .join(storage_query, storage_query.c.id == Machine.c.id, isouter=True)
        .join(
            fabrics_cte, fabrics_cte.c.machine_id == Machine.c.id, isouter=True
        )
        .join(
            spaces_cte, spaces_cte.c.machine_id == Machine.c.id, isouter=True
        )
        .join(
            MachineParent,
            MachineParent.c.id == Machine.c.parent_id,
            isouter=True,
        )
        .join(boot_interface_cte, boot_interface_cte.c.id == Machine.c.id)
        .join(extra_macs_cte, extra_macs_cte.c.id == Machine.c.id)
        .join(
            BootInterface,
            BootInterface.c.id == boot_interface_cte.c.boot_interface_id,
            isouter=True,
        )
        .join(BMC, BMC.c.id == Machine.c.bmc_id, isouter=True)
        .join(BootVlan, BootVlan.c.id == BootInterface.c.vlan_id)
        .join(BootFabric, BootFabric.c.id == BootVlan.c.fabric_id)
        .join(
            ip_addresses_cte,
            ip_addresses_cte.c.id == Machine.c.id,
            isouter=True,
        )
        .join(
            discovered_machine_addresses_cte,
            discovered_machine_addresses_cte.c.id == Machine.c.id,
            isouter=True,
        )
        .join(
            testing_status_cte,
            testing_status_cte.c.id == Machine.c.id,
            isouter=True,
        )
        .join(
            tags_cte,
            tags_cte.c.id == Machine.c.id,
        )
        .where(
            Machine.c.node_type == NODE_TYPE.MACHINE,
        )
        .order_by(Machine.c.id)
        .limit(limit)
    )
    return stmt


def get_machines(rows, admin):
    machines = []
    for row in rows:
        machine = {key: getattr(row, key) for key in PLAIN_LIST_ATTRIBUTES}
        machine.update(
            {
                "memory": row.memory,
                "status": NODE_STATUS_CHOICES_DICT[row.status_code],
                "status_code": row.status_code,
                "simple_status": SIMPLIFIED_NODE_STATUSES_MAP_REVERSED.get(
                    row.status_code, SIMPLIFIED_NODE_STATUS.OTHER
                ),
                "domain": {"id": row.domain_id, "name": row.domain_name},
                "pool": {"id": row.pool_id, "name": row.pool_name},
                "zone": {"id": row.zone_id, "name": row.zone_name},
                "fqdn": f"{row.hostname}.{row.domain_name}",
                "owner": row.owner_name,
                "parent": row.parent,
                # XXX: Need better permission check.
                "permissions": ["edit", "delete"]
                if admin.is_superuser
                else None,
                "link_type": NODE_TYPE_TO_LINK_TYPE[row.node_type],
                "tags": row.tag_ids,
                "physical_disk_count": row.disk_count,
                "storage": row.storage,
                "fabrics": row.fabrics,
                "spaces": row.spaces,
                "extra_macs": row.extra_macs,
                "pxe_mac": row.pxe_mac,
                "power_type": row.power_type,
                "status_message": row.status_message,
                "ip_addresses": [
                    {"ip": ip, "is_boot": is_boot}
                    for ip, is_boot in zip(row.ips, row.is_boot_ips)
                    if ip
                ],
                "vlan": {
                    "id": row.boot_vlan_id,
                    "name": str(row.boot_vlan_name),
                    "fabric_id": row.boot_fabric_id,
                    "fabric_name": row.boot_fabric_name,
                },
                "testing_status": {
                    "failed": row.testing_status_failed,
                    "passed": row.testing_status_passed,
                    "pending": row.testing_status_pending,
                    "running": row.testing_status_running,
                    "status": row.testing_status_combined,
                },
                "storage_test_status": {
                    "failed": row.storage_test_status_failed,
                    "passed": row.storage_test_status_passed,
                    "pending": row.storage_test_status_pending,
                    "running": row.storage_test_status_running,
                    "status": row.storage_test_status_combined,
                },
                "network_test_status": {
                    "failed": row.network_test_status_failed,
                    "passed": row.network_test_status_passed,
                    "pending": row.network_test_status_pending,
                    "running": row.network_test_status_running,
                    "status": row.network_test_status_combined,
                },
                "memory_test_status": {
                    "failed": row.memory_test_status_failed,
                    "passed": row.memory_test_status_passed,
                    "pending": row.memory_test_status_pending,
                    "running": row.memory_test_status_running,
                    "status": row.memory_test_status_combined,
                },
                "cpu_test_status": {
                    "failed": row.cpu_test_status_failed,
                    "passed": row.cpu_test_status_passed,
                    "pending": row.cpu_test_status_pending,
                    "running": row.cpu_test_status_running,
                    "status": row.cpu_test_status_combined,
                },
            }
        )
        machines.append(machine)
    return machines


def list_machines_multiple_queries(conn, admin, limit=None):
    """Use SQLAlchemy core to get the data in multiple query."""
    MachineParent = Machine.alias("parent")
    stmt = (
        select(
            *[getattr(Machine.c, attr) for attr in PLAIN_LIST_ATTRIBUTES],
            Machine.c.domain_id,
            Machine.c.node_type,
            Machine.c.pool_id,
            Machine.c.status.label("status_code"),
            Machine.c.zone_id,
            Domain.c.name.label("domain_name"),
            func.coalesce(User.c.username, "").label("owner_name"),
            MachineParent.c.system_id.label("parent"),
            ResourcePool.c.name.label("pool_name"),
            Zone.c.name.label("zone_name"),
            func.round((Machine.c.memory / 1024), 1).label("memory"),
            BMC.c.power_type,
        )
        .select_from(Machine)
        .join(Domain, Domain.c.id == Machine.c.domain_id)
        .join(User, isouter=True)
        .join(
            ResourcePool, ResourcePool.c.id == Machine.c.pool_id, isouter=True
        )
        .join(Zone, Zone.c.id == Machine.c.zone_id, isouter=True)
        .join(
            MachineParent,
            MachineParent.c.id == Machine.c.parent_id,
            isouter=True,
        )
        .join(BMC, BMC.c.id == Machine.c.bmc_id, isouter=True)
        .where(
            Machine.c.node_type == NODE_TYPE.MACHINE,
        )
        .order_by(Machine.c.id)
        .limit(limit)
    )
    machine_rows = list(conn.execute(stmt))
    tags_stmt = (
        select(
            Machine.c.id,
            postgresql.array_agg(NodeTag.c.tag_id).label("tag_ids"),
        )
        .select_from(Machine)
        .join(NodeTag, NodeTag.c.node_id == Machine.c.id)
        .group_by(Machine.c.id)
        .where(
            Machine.c.node_type == NODE_TYPE.MACHINE,
        )
        .order_by(Machine.c.id)
        .limit(limit)
    )

    network_stmt = (
        select(
            Machine.c.id,
            postgresql.array_agg(func.distinct(Fabric.c.name)).label(
                "fabrics"
            ),
            func.coalesce(
                postgresql.array_agg(func.distinct(Space.c.name)), []
            ).label("spaces"),
        )
        .select_from(Machine)
        .join(NodeConfig, Machine.c.current_config_id == NodeConfig.c.id)
        .join(Interface, NodeConfig.c.id == Interface.c.node_config_id)
        .join(Vlan, Interface.c.vlan_id == Vlan.c.id)
        .join(Fabric, Fabric.c.id == Vlan.c.fabric_id)
        .join(Space, Space.c.id == Vlan.c.space_id, isouter=True)
        .where(
            Machine.c.node_type == NODE_TYPE.MACHINE,
        )
        .group_by(Machine.c.id)
        .order_by(Machine.c.id)
        .limit(limit)
    )

    storage_stmt = (
        select(
            Machine.c.id,
            func.count(PhysicalBlockDevice.c.blockdevice_ptr_id).label(
                "disk_count"
            ),
            func.round(
                func.sum(func.coalesce(BlockDevice.c.size, 0)) / 1000**3,
                1,
            ).label("storage"),
        )
        .select_from(Machine)
        .join(NodeConfig, Machine.c.id == NodeConfig.c.node_id)
        .join(
            BlockDevice,
            NodeConfig.c.id == BlockDevice.c.node_config_id,
            isouter=True,
        )
        .join(
            PhysicalBlockDevice,
            BlockDevice.c.id == PhysicalBlockDevice.c.blockdevice_ptr_id,
        )
        .where(
            Machine.c.node_type == NODE_TYPE.MACHINE,
        )
        .group_by(Machine.c.id)
        .order_by(Machine.c.id)
        .limit(limit)
    )

    boot_interface_cte = (
        select(
            Machine.c.id,
            func.coalesce(Machine.c.boot_interface_id, Interface.c.id).label(
                "boot_interface_id"
            ),
        )
        .select_from(Machine)
        .distinct(Machine.c.id)
        .join(NodeConfig, NodeConfig.c.id == Machine.c.current_config_id)
        .join(Interface, Interface.c.node_config_id == NodeConfig.c.id)
        .where(
            Interface.c.type == INTERFACE_TYPE.PHYSICAL,
        )
        .order_by(Machine.c.id, Interface.c.id.asc())
    ).cte("boot_interface_cte")
    extra_macs_cte = (
        select(
            Machine.c.id,
            postgresql.array_agg(Interface.c.mac_address).label("extra_macs"),
        )
        .join(NodeConfig, NodeConfig.c.id == Machine.c.current_config_id)
        .join(Interface, Interface.c.node_config_id == NodeConfig.c.id)
        .join(boot_interface_cte, boot_interface_cte.c.id == Machine.c.id)
        .where(
            Interface.c.id != boot_interface_cte.c.boot_interface_id,
            Interface.c.type == INTERFACE_TYPE.PHYSICAL,
        )
        .group_by(Machine.c.id)
    ).cte("extra_macs")
    boot_stmt = (
        select(
            Machine.c.id,
            Vlan.c.id.label("boot_vlan_id"),
            Vlan.c.name.label("boot_vlan_name"),
            Vlan.c.fabric_id.label("boot_fabric_id"),
            Fabric.c.name.label("boot_fabric_name"),
            Interface.c.mac_address.label("pxe_mac"),
            extra_macs_cte.c.extra_macs,
        )
        .join(boot_interface_cte, boot_interface_cte.c.id == Machine.c.id)
        .join(extra_macs_cte, extra_macs_cte.c.id == Machine.c.id)
        .join(
            Interface,
            Interface.c.id == boot_interface_cte.c.boot_interface_id,
            isouter=True,
        )
        .join(Vlan, Vlan.c.id == Interface.c.vlan_id)
        .join(Fabric, Fabric.c.id == Vlan.c.fabric_id)
        .where(
            Machine.c.node_type == NODE_TYPE.MACHINE,
        )
        .order_by(Machine.c.id)
        .limit(limit)
    )

    status_message_subquery = (
        select(
            func.concat(
                EventType.c.description,
                " - ",
                Event.c.description,
            ).label("status_message"),
        )
        .select_from(Event)
        .join(EventType, EventType.c.id == Event.c.type_id)
        .order_by(Event.c.node_id, Event.c.created.desc(), Event.c.id.desc())
        .where(
            Machine.c.id == Event.c.node_id,
            EventType.c.level >= logging.INFO,
        )
        .limit(1)
    ).scalar_subquery()
    status_message_stmt = (
        select(
            Machine.c.id,
            status_message_subquery.label("status_message"),
        )
        .select_from(Machine)
        .where(
            Machine.c.node_type == NODE_TYPE.MACHINE,
        )
        .order_by(Machine.c.id)
        .limit(limit)
    )

    interfaces_cte = (
        select(
            Machine.c.id.label("machine_id"),
            Interface.c.id.label("interface_id"),
        )
        .select_from(Interface)
        .join(NodeConfig, NodeConfig.c.id == Interface.c.node_config_id)
        .join(Machine, Machine.c.current_config_id == NodeConfig.c.id)
    ).cte("interfaces")
    discovered_addresses_cte = (
        select(
            Interface.c.id,
            StaticIPAddress.c.ip,
        )
        .select_from(Interface)
        .join(
            InterfaceIPAddresses,
            Interface.c.id == InterfaceIPAddresses.c.interface_id,
        )
        .join(
            StaticIPAddress,
            InterfaceIPAddresses.c.staticipaddress_id == StaticIPAddress.c.id,
        )
        .where(
            StaticIPAddress.c.alloc_type == IPADDRESS_TYPE.DISCOVERED,
            StaticIPAddress.c.ip.is_not(None),
        )
    ).cte("discovered_addresses")

    DiscoveredAddress = StaticIPAddress.alias("discovered_ip")
    DiscoveredInterfaceIPAddresses = InterfaceIPAddresses.alias(
        "discovered_interface_ip"
    )
    dhcp_address_cte = (
        select(
            StaticIPAddress.c.id,
            DiscoveredAddress.c.ip,
        )
        .select_from(StaticIPAddress)
        .distinct(StaticIPAddress.c.id)
        .join(
            InterfaceIPAddresses,
            InterfaceIPAddresses.c.staticipaddress_id == StaticIPAddress.c.id,
        )
        .join(
            DiscoveredInterfaceIPAddresses,
            DiscoveredInterfaceIPAddresses.c.interface_id
            == InterfaceIPAddresses.c.interface_id,
        )
        .join(
            DiscoveredAddress,
            DiscoveredAddress.c.id
            == InterfaceIPAddresses.c.staticipaddress_id,
        )
        .where(
            StaticIPAddress.c.alloc_type == IPADDRESS_TYPE.DHCP,
            DiscoveredAddress.c.alloc_type == IPADDRESS_TYPE.DISCOVERED,
            DiscoveredAddress.c.ip.is_not(None),
        )
        .order_by(StaticIPAddress.c.id, DiscoveredAddress.c.id.desc())
    ).cte("dhcp_address")
    interface_addresses_cte = (
        select(
            Interface.c.id,
            case(
                (
                    StaticIPAddress.c.alloc_type == IPADDRESS_TYPE.DHCP,
                    dhcp_address_cte.c.ip,
                ),
                else_=StaticIPAddress.c.ip,
            ).label("ip"),
        )
        .select_from(Interface)
        .join(
            InterfaceIPAddresses,
            Interface.c.id == InterfaceIPAddresses.c.interface_id,
        )
        .join(
            StaticIPAddress,
            InterfaceIPAddresses.c.staticipaddress_id == StaticIPAddress.c.id,
        )
        .join(
            dhcp_address_cte,
            dhcp_address_cte.c.id == StaticIPAddress.c.id,
            isouter=True,
        )
    ).cte("interface_addresses")
    ip_addresses_cte = (
        select(
            Machine.c.id,
            postgresql.array_agg(interface_addresses_cte.c.ip).label("ips"),
            postgresql.array_agg(
                interface_addresses_cte.c.id
                == boot_interface_cte.c.boot_interface_id
            ).label("is_boot_ips"),
        )
        .select_from(Machine)
        .join(interfaces_cte, interfaces_cte.c.machine_id == Machine.c.id)
        .join(
            interface_addresses_cte,
            interface_addresses_cte.c.id == interfaces_cte.c.interface_id,
        )
        .join(boot_interface_cte, boot_interface_cte.c.id == Machine.c.id)
        .group_by(Machine.c.id)
    ).cte("ip_addresses")
    discovered_machine_addresses_cte = (
        select(
            Machine.c.id,
            postgresql.array_agg(discovered_addresses_cte.c.ip).label("ips"),
            postgresql.array_agg(
                discovered_addresses_cte.c.id
                == boot_interface_cte.c.boot_interface_id
            ).label("is_boot_ips"),
        )
        .select_from(Machine)
        .join(interfaces_cte, interfaces_cte.c.machine_id == Machine.c.id)
        .join(
            discovered_addresses_cte,
            discovered_addresses_cte.c.id == interfaces_cte.c.interface_id,
        )
        .join(boot_interface_cte, boot_interface_cte.c.id == Machine.c.id)
        .group_by(Machine.c.id)
    ).cte("discovered_machine_ip_addresses")
    ip_stmt = (
        select(
            Machine.c.id,
            case(
                (
                    ip_addresses_cte.c.ips.is_(None),
                    discovered_machine_addresses_cte.c.ips,
                ),
                else_=ip_addresses_cte.c.ips,
            ).label("ips"),
            case(
                (
                    ip_addresses_cte.c.ips.is_(None),
                    discovered_machine_addresses_cte.c.is_boot_ips,
                ),
                else_=ip_addresses_cte.c.is_boot_ips,
            ).label("is_boot_ips"),
        )
        .select_from(Machine)
        # .join(boot_interface_cte, boot_interface_cte.c.id == Machine.c.id)
        .join(
            ip_addresses_cte,
            ip_addresses_cte.c.id == Machine.c.id,
            isouter=True,
        )
        .join(
            discovered_machine_addresses_cte,
            discovered_machine_addresses_cte.c.id == Machine.c.id,
            isouter=True,
        )
        .where(
            Machine.c.node_type == NODE_TYPE.MACHINE,
        )
        .order_by(Machine.c.id)
        .limit(limit)
    )

    testing_status_cte = (
        select(
            Machine.c.id,
            func.sum(
                case(
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("testing_status_pending"),
            func.sum(
                case(
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    else_=0,
                ),
            ).label("testing_status_running"),
            func.sum(
                case(
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("testing_status_passed"),
            func.sum(
                case(
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("testing_status_failed"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.APPLYING_NETCONF,
                        1,
                    ),
                    (ScriptResult.c.status == SCRIPT_STATUS.INSTALLING, 1),
                    else_=0,
                ),
            ).label("testing_status_combined_running"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("testing_status_combined_failed"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("testing_status_combined_pending"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    else_=0,
                ),
            ).label("testing_status_combined_aborted"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.DEGRADED, 1),
                    else_=0,
                ),
            ).label("testing_status_combined_degraded"),
            func.sum(
                case(
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("testing_status_combined_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("storage_test_status_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    else_=0,
                ),
            ).label("storage_test_status_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("storage_test_status_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("storage_test_status_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.APPLYING_NETCONF,
                        1,
                    ),
                    (ScriptResult.c.status == SCRIPT_STATUS.INSTALLING, 1),
                    else_=0,
                ),
            ).label("storage_test_status_combined_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("storage_test_status_combined_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("storage_test_status_combined_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    else_=0,
                ),
            ).label("storage_test_status_combined_aborted"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.DEGRADED, 1),
                    else_=0,
                ),
            ).label("storage_test_status_combined_degraded"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.STORAGE, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("storage_test_status_combined_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("network_test_status_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    else_=0,
                ),
            ).label("network_test_status_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("network_test_status_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("network_test_status_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.APPLYING_NETCONF,
                        1,
                    ),
                    (ScriptResult.c.status == SCRIPT_STATUS.INSTALLING, 1),
                    else_=0,
                ),
            ).label("network_test_status_combined_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("network_test_status_combined_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("network_test_status_combined_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    else_=0,
                ),
            ).label("network_test_status_combined_aborted"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.DEGRADED, 1),
                    else_=0,
                ),
            ).label("network_test_status_combined_degraded"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.NETWORK, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("network_test_status_combined_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("memory_test_status_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    else_=0,
                ),
            ).label("memory_test_status_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("memory_test_status_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("memory_test_status_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.APPLYING_NETCONF,
                        1,
                    ),
                    (ScriptResult.c.status == SCRIPT_STATUS.INSTALLING, 1),
                    else_=0,
                ),
            ).label("memory_test_status_combined_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("memory_test_status_combined_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("memory_test_status_combined_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    else_=0,
                ),
            ).label("memory_test_status_combined_aborted"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.DEGRADED, 1),
                    else_=0,
                ),
            ).label("memory_test_status_combined_degraded"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.MEMORY, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("memory_test_status_combined_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_passed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("cpu_test_status_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.RUNNING, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.APPLYING_NETCONF,
                        1,
                    ),
                    (ScriptResult.c.status == SCRIPT_STATUS.INSTALLING, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_running"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.FAILED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.TIMEDOUT, 1),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_INSTALLING,
                        1,
                    ),
                    (
                        ScriptResult.c.status
                        == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                        1,
                    ),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_failed"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PENDING, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_pending"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.ABORTED, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_aborted"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.DEGRADED, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_degraded"),
            func.sum(
                case(
                    (Script.c.hardware_type != HARDWARE_TYPE.CPU, 0),
                    (ScriptResult.c.suppressed, 0),
                    (ScriptResult.c.status == SCRIPT_STATUS.PASSED, 1),
                    (ScriptResult.c.status == SCRIPT_STATUS.SKIPPED, 1),
                    else_=0,
                ),
            ).label("cpu_test_status_combined_passed"),
        )
        .select_from(Machine)
        .join(ScriptSet, ScriptSet.c.node_id == Machine.c.id)
        .join(ScriptResult, ScriptResult.c.script_set_id == ScriptSet.c.id)
        .join(Script, Script.c.id == ScriptResult.c.script_id)
        .where(ScriptSet.c.result_type == RESULT_TYPE.TESTING)
        .group_by(Machine.c.id)
    ).cte("testing_status")
    testing_stmt = (
        select(
            Machine.c.id,
            testing_status_cte.c.testing_status_pending,
            testing_status_cte.c.testing_status_running,
            testing_status_cte.c.testing_status_passed,
            testing_status_cte.c.testing_status_failed,
            case(
                (
                    testing_status_cte.c.testing_status_combined_running > 0,
                    SCRIPT_STATUS.RUNNING,
                ),
                (
                    testing_status_cte.c.testing_status_combined_failed > 0,
                    SCRIPT_STATUS.FAILED,
                ),
                (
                    testing_status_cte.c.testing_status_combined_pending > 0,
                    SCRIPT_STATUS.PENDING,
                ),
                (
                    testing_status_cte.c.testing_status_combined_degraded > 0,
                    SCRIPT_STATUS.DEGRADED,
                ),
                (
                    testing_status_cte.c.testing_status_combined_passed > 0,
                    SCRIPT_STATUS.PASSED,
                ),
                else_=-1,
            ).label("testing_status_combined"),
            testing_status_cte.c.storage_test_status_pending,
            testing_status_cte.c.storage_test_status_running,
            testing_status_cte.c.storage_test_status_passed,
            testing_status_cte.c.storage_test_status_failed,
            case(
                (
                    testing_status_cte.c.storage_test_status_combined_running
                    > 0,
                    SCRIPT_STATUS.RUNNING,
                ),
                (
                    testing_status_cte.c.storage_test_status_combined_failed
                    > 0,
                    SCRIPT_STATUS.FAILED,
                ),
                (
                    testing_status_cte.c.storage_test_status_combined_pending
                    > 0,
                    SCRIPT_STATUS.PENDING,
                ),
                (
                    testing_status_cte.c.storage_test_status_combined_degraded
                    > 0,
                    SCRIPT_STATUS.DEGRADED,
                ),
                (
                    testing_status_cte.c.storage_test_status_combined_passed
                    > 0,
                    SCRIPT_STATUS.PASSED,
                ),
                else_=-1,
            ).label("storage_test_status_combined"),
            testing_status_cte.c.network_test_status_pending,
            testing_status_cte.c.network_test_status_running,
            testing_status_cte.c.network_test_status_passed,
            testing_status_cte.c.network_test_status_failed,
            case(
                (
                    testing_status_cte.c.network_test_status_combined_running
                    > 0,
                    SCRIPT_STATUS.RUNNING,
                ),
                (
                    testing_status_cte.c.network_test_status_combined_failed
                    > 0,
                    SCRIPT_STATUS.FAILED,
                ),
                (
                    testing_status_cte.c.network_test_status_combined_pending
                    > 0,
                    SCRIPT_STATUS.PENDING,
                ),
                (
                    testing_status_cte.c.network_test_status_combined_degraded
                    > 0,
                    SCRIPT_STATUS.DEGRADED,
                ),
                (
                    testing_status_cte.c.network_test_status_combined_passed
                    > 0,
                    SCRIPT_STATUS.PASSED,
                ),
                else_=-1,
            ).label("network_test_status_combined"),
            testing_status_cte.c.cpu_test_status_pending,
            testing_status_cte.c.cpu_test_status_running,
            testing_status_cte.c.cpu_test_status_passed,
            testing_status_cte.c.cpu_test_status_failed,
            case(
                (
                    testing_status_cte.c.cpu_test_status_combined_running > 0,
                    SCRIPT_STATUS.RUNNING,
                ),
                (
                    testing_status_cte.c.cpu_test_status_combined_failed > 0,
                    SCRIPT_STATUS.FAILED,
                ),
                (
                    testing_status_cte.c.cpu_test_status_combined_pending > 0,
                    SCRIPT_STATUS.PENDING,
                ),
                (
                    testing_status_cte.c.cpu_test_status_combined_degraded > 0,
                    SCRIPT_STATUS.DEGRADED,
                ),
                (
                    testing_status_cte.c.cpu_test_status_combined_passed > 0,
                    SCRIPT_STATUS.PASSED,
                ),
                else_=-1,
            ).label("cpu_test_status_combined"),
            testing_status_cte.c.memory_test_status_pending,
            testing_status_cte.c.memory_test_status_running,
            testing_status_cte.c.memory_test_status_passed,
            testing_status_cte.c.memory_test_status_failed,
            case(
                (
                    testing_status_cte.c.memory_test_status_combined_running
                    > 0,
                    SCRIPT_STATUS.RUNNING,
                ),
                (
                    testing_status_cte.c.memory_test_status_combined_failed
                    > 0,
                    SCRIPT_STATUS.FAILED,
                ),
                (
                    testing_status_cte.c.memory_test_status_combined_pending
                    > 0,
                    SCRIPT_STATUS.PENDING,
                ),
                (
                    testing_status_cte.c.memory_test_status_combined_degraded
                    > 0,
                    SCRIPT_STATUS.DEGRADED,
                ),
                (
                    testing_status_cte.c.memory_test_status_combined_passed
                    > 0,
                    SCRIPT_STATUS.PASSED,
                ),
                else_=-1,
            ).label("memory_test_status_combined"),
        )
        .select_from(Machine)
        .join(
            testing_status_cte,
            testing_status_cte.c.id == Machine.c.id,
            isouter=True,
        )
        .where(
            Machine.c.node_type == NODE_TYPE.MACHINE,
        )
        .order_by(Machine.c.id)
        .limit(limit)
    )

    machine_tags = {row.id: row.tag_ids for row in conn.execute(tags_stmt)}

    machine_networks = {row.id: row for row in conn.execute(network_stmt)}

    machine_storage = {row.id: row for row in conn.execute(storage_stmt)}

    machine_boot = {row.id: row for row in conn.execute(boot_stmt)}
    machine_status_message = {
        row.id: row for row in conn.execute(status_message_stmt)
    }
    machine_ips = {row.id: row for row in conn.execute(ip_stmt)}
    machine_testing = {row.id: row for row in conn.execute(testing_stmt)}

    machines = []
    for row in machine_rows:
        machine = {key: getattr(row, key) for key in PLAIN_LIST_ATTRIBUTES}
        machine.update(
            {
                "memory": row.memory,
                "status": NODE_STATUS_CHOICES_DICT[row.status_code],
                "status_code": row.status_code,
                "simple_status": SIMPLIFIED_NODE_STATUSES_MAP_REVERSED.get(
                    row.status_code, SIMPLIFIED_NODE_STATUS.OTHER
                ),
                "domain": {"id": row.domain_id, "name": row.domain_name},
                "pool": {"id": row.pool_id, "name": row.pool_name},
                "zone": {"id": row.zone_id, "name": row.zone_name},
                "fqdn": f"{row.hostname}.{row.domain_name}",
                "owner": row.owner_name,
                "parent": row.parent,
                # XXX: Need better permission check.
                "permissions": ["edit", "delete"]
                if admin.is_superuser
                else None,
                "link_type": NODE_TYPE_TO_LINK_TYPE[row.node_type],
                "tags": machine_tags[row.id],
                "physical_disk_count": machine_storage[row.id].disk_count,
                "storage": machine_storage[row.id].storage,
                "fabrics": machine_networks[row.id].fabrics,
                "spaces": [
                    space for space in machine_networks[row.id].spaces if space
                ],
                "extra_macs": machine_boot[row.id].extra_macs,
                "pxe_mac": machine_boot[row.id].pxe_mac,
                "power_type": row.power_type,
                "status_message": machine_status_message[
                    row.id
                ].status_message,
                "ip_addresses": [
                    {"ip": ip, "is_boot": is_boot}
                    for ip, is_boot in zip(
                        machine_ips[row.id].ips,
                        machine_ips[row.id].is_boot_ips,
                    )
                    if ip
                ],
                "vlan": {
                    "id": machine_boot[row.id].boot_vlan_id,
                    "name": str(machine_boot[row.id].boot_vlan_name),
                    "fabric_id": machine_boot[row.id].boot_fabric_id,
                    "fabric_name": machine_boot[row.id].boot_fabric_name,
                },
                "testing_status": {
                    "failed": machine_testing[row.id].testing_status_failed,
                    "passed": machine_testing[row.id].testing_status_passed,
                    "pending": machine_testing[row.id].testing_status_pending,
                    "running": machine_testing[row.id].testing_status_running,
                    "status": machine_testing[row.id].testing_status_combined,
                },
                "storage_test_status": {
                    "failed": machine_testing[
                        row.id
                    ].storage_test_status_failed,
                    "passed": machine_testing[
                        row.id
                    ].storage_test_status_passed,
                    "pending": machine_testing[
                        row.id
                    ].storage_test_status_pending,
                    "running": machine_testing[
                        row.id
                    ].storage_test_status_running,
                    "status": machine_testing[
                        row.id
                    ].storage_test_status_combined,
                },
                "network_test_status": {
                    "failed": machine_testing[
                        row.id
                    ].network_test_status_failed,
                    "passed": machine_testing[
                        row.id
                    ].network_test_status_passed,
                    "pending": machine_testing[
                        row.id
                    ].network_test_status_pending,
                    "running": machine_testing[
                        row.id
                    ].network_test_status_running,
                    "status": machine_testing[
                        row.id
                    ].network_test_status_combined,
                },
                "memory_test_status": {
                    "failed": machine_testing[
                        row.id
                    ].memory_test_status_failed,
                    "passed": machine_testing[
                        row.id
                    ].memory_test_status_passed,
                    "pending": machine_testing[
                        row.id
                    ].memory_test_status_pending,
                    "running": machine_testing[
                        row.id
                    ].memory_test_status_running,
                    "status": machine_testing[
                        row.id
                    ].memory_test_status_combined,
                },
                "cpu_test_status": {
                    "failed": machine_testing[row.id].cpu_test_status_failed,
                    "passed": machine_testing[row.id].cpu_test_status_passed,
                    "pending": machine_testing[row.id].cpu_test_status_pending,
                    "running": machine_testing[row.id].cpu_test_status_running,
                    "status": machine_testing[row.id].cpu_test_status_combined,
                },
            }
        )
        machines.append(machine)
    return machines
