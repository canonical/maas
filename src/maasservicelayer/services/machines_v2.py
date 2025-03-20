#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
import logging
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import case, desc, distinct, or_, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.expression import ColumnOperators, func

from maascommon.enums.bmc import BmcType
from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.node import SimplifiedNodeStatusEnum
from maasserver.enum import (
    NODE_STATUS_CHOICES_DICT,
    SIMPLIFIED_NODE_STATUSES_MAP_REVERSED,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import (
    BlockDeviceTable,
    BMCTable,
    DomainTable,
    EventTable,
    EventTypeTable,
    FabricTable,
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    NodeTagTable,
    PhysicalBlockDeviceTable,
    ResourcePoolTable,
    ScriptResultTable,
    ScriptSetTable,
    ScriptTable,
    SpaceTable,
    StaticIPAddressTable,
    SubnetTable,
    UserTable,
    VlanTable,
    ZoneTable,
)
from maasservicelayer.services.base import Service
from metadataserver.enum import HARDWARE_TYPE, RESULT_TYPE, SCRIPT_STATUS


# Requests
class MachineRequest(BaseModel):
    id: int
    actions: list[str]
    permissions: list[str]


class MachineListGroupRequest(BaseModel):
    name: Optional[str]
    value: Optional[str]
    count: Optional[int]
    collapsed: Optional[bool]
    items: list[MachineRequest]


class MachineListRequest(BaseModel):
    count: int
    cur_page: int
    num_pages: int
    groups: list[MachineListGroupRequest]


# Entities
class ModelRef(BaseModel):
    id: int
    name: str


class TestStatus(BaseModel):
    status: Optional[int]
    pending: Optional[int]
    running: Optional[int]
    passed: Optional[int]
    failed: Optional[int]


class Vlan(BaseModel):
    id: Optional[int]
    name: Optional[str]
    fabric_id: Optional[int]
    fabric_name: Optional[str]


class IPAddress(BaseModel):
    ip: Optional[str]
    is_boot: Optional[bool]


class Machine(BaseModel):
    # maasui/src/src/app/store/machine/types/base.ts

    id: int
    system_id: str
    hostname: str
    description: str
    pool: ModelRef
    pod: Optional[ModelRef]
    domain: ModelRef
    owner: str
    parent: Optional[str]
    error_description: str
    zone: ModelRef
    cpu_count: int
    memory: int
    power_state: str
    locked: bool
    permissions: list[str]
    fqdn: str
    actions: list[str]
    link_type: str
    tags: Optional[list[int]]
    physical_disk_count: Optional[int]
    storage: Optional[float]
    testing_status: Optional[TestStatus]
    architecture: str
    osystem: str
    distro_series: str
    status: str
    status_code: int
    simple_status: str
    ephemeral_deploy: bool
    fabrics: Optional[list[str]]
    spaces: Optional[list[str]]
    extra_macs: Optional[list[str]]
    status_message: Optional[str]
    pxe_mac: Optional[str]
    vlan: Optional[Vlan]
    power_type: Optional[str]
    ip_addresses: Optional[list[IPAddress]]
    cpu_test_status: Optional[TestStatus]
    memory_test_status: Optional[TestStatus]
    network_test_status: Optional[TestStatus]
    storage_test_status: Optional[TestStatus]
    is_dpu: bool


# Responses
class MachineListGroupResponse(BaseModel):
    name: Optional[str]
    value: Optional[str]
    count: Optional[int]
    collapsed: Optional[bool]
    items: Optional[list[Machine]]


class MachineListResponse(BaseModel):
    count: int
    cur_page: int
    num_pages: int
    groups: Optional[list[MachineListGroupResponse]]


class MachinesV2Service(Service, Repository):
    """
    TL;DR DO NOT USE THIS!

    This service was part of the first iteration of the maasapiserver. maasserver used to make a POST query to the apiserver to
    retrieve the machine listing. After that initial iteration, we decided to implement the v3 api and we integrated the
    service layer with maasserver. For this reason, we moved that logic to the service layer so that the websocket handlers can call this method directly.
    This service MUST be removed when the websocket handler for the machine list is removed - do not use this anymore!
    """

    def __init__(self, context: Context):
        super().__init__(context)

    async def list(self, request: MachineListRequest) -> MachineListResponse:
        ids = []
        for group in request.groups:
            ids += list(map(lambda x: x.id, group.items))

        stmt = self._single_query(ids)
        result = await self.execute_stmt(stmt)

        machines = {}
        for row in result.all():
            machine = self._build_node(row._asdict())
            machines[machine.id] = machine

        groups = []
        for group in request.groups:
            groups.append(
                MachineListGroupResponse(
                    name=group.name,
                    value=group.value,
                    count=group.count,
                    collapsed=group.collapsed,
                    items=[
                        self._patch_machine(
                            machines[machine.id],
                            machine.actions,
                            machine.permissions,
                        )
                        for machine in group.items
                    ],
                )
            )
        response = MachineListResponse(
            count=request.count,
            cur_page=request.cur_page,
            num_pages=request.num_pages,
            groups=groups,
        )
        return response

    def _patch_machine(self, machine, actions, permissions):
        machine.actions = actions
        machine.permissions = permissions
        return machine

    def _build_node(self, record: dict):
        vlan = None
        if (
            record["boot_vlan_id"]
            or record["boot_vlan_name"]
            or record["boot_fabric_id"]
            or record["boot_fabric_name"]
        ):
            vlan = Vlan(
                id=record["boot_vlan_id"],
                name=record["boot_vlan_name"],
                fabric_id=record["boot_fabric_id"],
                fabric_name=record["boot_fabric_name"],
            )

        pod = None

        if record["pod_id"] or record["pod_name"]:
            pod = ModelRef(id=record["pod_id"], name=record["pod_name"])

        ip_addresses = []
        if record["ips"] and record["is_boot_ips"]:
            for i in range(len(record["ips"])):
                ip_addresses.append(
                    IPAddress(
                        ip=str(record["ips"][i]),
                        is_boot=record["is_boot_ips"][i],
                    )
                )
        if not record["pxe_mac"]:
            ip_addresses = None
            record["power_type"] = None

        machine = Machine(
            id=record["id"],
            system_id=record["system_id"],
            hostname=record["hostname"],
            description=record["description"],
            pool=ModelRef(id=record["pool_id"], name=record["pool_name"]),
            pod=pod,
            domain=ModelRef(
                id=record["domain_id"], name=record["domain_name"]
            ),
            owner=record["owner"],
            parent=record["parent"],
            error_description=record["error_description"],
            zone=ModelRef(id=record["zone_id"], name=record["zone_name"]),
            cpu_count=record["cpu_count"],
            memory=record["memory"],
            power_state=record["power_state"],
            locked=record["locked"],
            permissions=[],
            fqdn=record["fqdn"],
            actions=[],
            # maasserver/websockets/handlers/node.py:103
            link_type="machine",
            tags=record["tags"],
            physical_disk_count=record["physical_disk_count"],
            storage=record["storage"],
            testing_status=TestStatus(
                status=record["testing_status_combined"],
                pending=-1,
                running=-1,
                passed=-1,
                failed=-1,
            ),
            architecture=record["architecture"],
            osystem=record["osystem"],
            distro_series=record["distro_series"],
            status=NODE_STATUS_CHOICES_DICT[record["status_code"]],
            status_code=record["status_code"],
            simple_status=SIMPLIFIED_NODE_STATUSES_MAP_REVERSED.get(
                record["status_code"], SimplifiedNodeStatusEnum.OTHER.value
            ),
            ephemeral_deploy=record["ephemeral_deploy"],
            fabrics=record["fabrics"],
            spaces=record["spaces"],
            extra_macs=record["extra_macs"],
            status_message=record["status_message"],
            pxe_mac=record["pxe_mac"],
            vlan=vlan,
            power_type=record["power_type"],
            ip_addresses=ip_addresses,
            cpu_test_status=TestStatus(
                status=record["cpu_test_status_combined"],
                pending=-1,
                running=-1,
                passed=-1,
                failed=-1,
            ),
            memory_test_status=TestStatus(
                status=record["memory_test_status_combined"],
                pending=-1,
                running=-1,
                passed=-1,
                failed=-1,
            ),
            network_test_status=TestStatus(
                status=record["network_test_status_combined"],
                pending=-1,
                running=-1,
                passed=-1,
                failed=-1,
            ),
            storage_test_status=TestStatus(
                status=record["storage_test_status_combined"],
                pending=-1,
                running=-1,
                passed=-1,
                failed=-1,
            ),
            is_dpu=record["is_dpu"],
        )
        return machine

    def _single_query(self, ids):
        storage_query = (
            select(
                NodeTable.c.id,
                func.count(
                    PhysicalBlockDeviceTable.c.blockdevice_ptr_id
                ).label("disk_count"),
                func.sum(func.coalesce(BlockDeviceTable.c.size, 0)).label(
                    "storage"
                ),
            )
            .select_from(PhysicalBlockDeviceTable)
            .join(
                BlockDeviceTable,
                BlockDeviceTable.c.id
                == PhysicalBlockDeviceTable.c.blockdevice_ptr_id,
            )
            .join(
                NodeConfigTable,
                NodeConfigTable.c.id == BlockDeviceTable.c.node_config_id,
            )
            .join(NodeTable, NodeTable.c.id == NodeConfigTable.c.node_id)
            .group_by(NodeTable.c.id)
        ).cte("storage")

        interfaces_cte = (
            select(
                NodeTable.c.id.label("node_id"),
                InterfaceTable.c.id.label("interface_id"),
            )
            .select_from(InterfaceTable)
            .join(
                NodeConfigTable,
                NodeConfigTable.c.id == InterfaceTable.c.node_config_id,
            )
            .join(
                NodeTable,
                NodeTable.c.current_config_id == NodeConfigTable.c.id,
            )
        ).cte("interfaces")

        vlans_cte = (
            select(
                VlanTable.c.id,
                VlanTable.c.fabric_id,
                VlanTable.c.space_id,
                NodeTable.c.id.label("node_id"),
            )
            .select_from(NodeTable)
            .join(
                NodeConfigTable,
                NodeTable.c.current_config_id == NodeConfigTable.c.id,
            )
            .join(
                InterfaceTable,
                NodeConfigTable.c.id == InterfaceTable.c.node_config_id,
                isouter=True,
            )
            .join(
                InterfaceIPAddressTable,
                InterfaceTable.c.id == InterfaceIPAddressTable.c.interface_id,
                isouter=True,
            )
            .join(
                StaticIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
                isouter=True,
            )
            .join(
                SubnetTable,
                SubnetTable.c.id == StaticIPAddressTable.c.subnet_id,
                isouter=True,
            )
            .join(
                VlanTable,
                or_(
                    VlanTable.c.id == SubnetTable.c.vlan_id,
                    VlanTable.c.id == InterfaceTable.c.vlan_id,
                ),
            )
        ).cte("vlans")

        fabrics_cte = (
            select(
                vlans_cte.c.node_id,
                postgresql.array_agg(func.distinct(FabricTable.c.name)).label(
                    "names"
                ),
            )
            .select_from(FabricTable)
            .join(vlans_cte, vlans_cte.c.fabric_id == FabricTable.c.id)
            .group_by(vlans_cte.c.node_id)
        ).cte("fabrics")

        spaces_cte = (
            select(
                vlans_cte.c.node_id,
                postgresql.array_agg(func.distinct(SpaceTable.c.name)).label(
                    "names"
                ),
            )
            .select_from(SpaceTable)
            .join(vlans_cte, vlans_cte.c.space_id == SpaceTable.c.id)
            .group_by(vlans_cte.c.node_id)
        ).cte("spaces")

        first_boot_interface_cte = (
            select(
                NodeTable.c.id,
                func.min(InterfaceTable.c.id).label("first_boot_interface_id"),
            )
            .select_from(NodeTable)
            .join(
                NodeConfigTable,
                NodeConfigTable.c.id == NodeTable.c.current_config_id,
            )
            .join(
                InterfaceTable,
                InterfaceTable.c.node_config_id == NodeConfigTable.c.id,
            )
            .where(NodeTable.c.boot_interface_id == None)  # noqa: E711
            .group_by(NodeTable.c.id)
        ).cte("first_boot_interface")

        boot_interface_ip_cte = (
            select(
                NodeTable.c.id,
                case(
                    (
                        NodeTable.c.boot_interface_id.is_not(None),
                        NodeTable.c.boot_interface_id,
                    ),
                    else_=first_boot_interface_cte.c.first_boot_interface_id,
                ).label("boot_interface_id"),
            )
            .select_from(NodeTable)
            .join(
                first_boot_interface_cte,
                first_boot_interface_cte.c.id == NodeTable.c.id,
                isouter=True,
            )
        ).cte("boot_interface_ip")

        extra_macs_cte = (
            select(
                NodeTable.c.id,
                postgresql.array_agg(
                    distinct(InterfaceTable.c.mac_address)
                ).label("extra_macs"),
            )
            .join(
                NodeConfigTable,
                NodeConfigTable.c.id == NodeTable.c.current_config_id,
            )
            .join(
                InterfaceTable,
                InterfaceTable.c.node_config_id == NodeConfigTable.c.id,
            )
            .join(
                boot_interface_ip_cte,
                boot_interface_ip_cte.c.id == NodeTable.c.id,
            )
            .where(
                InterfaceTable.c.id
                != boot_interface_ip_cte.c.boot_interface_id,
                InterfaceTable.c.type == InterfaceType.PHYSICAL,
            )
            .group_by(NodeTable.c.id)
        ).cte("extra_macs")

        status_message_subquery = (
            select(
                func.concat(
                    EventTypeTable.c.description,
                    " - ",
                    EventTable.c.description,
                ).label("status_message"),
            )
            .select_from(EventTable)
            .join(EventTypeTable, EventTypeTable.c.id == EventTable.c.type_id)
            .order_by(
                EventTable.c.node_id,
                EventTable.c.created.desc(),
                EventTable.c.id.desc(),
            )
            .where(
                NodeTable.c.id == EventTable.c.node_id,
                EventTypeTable.c.level >= logging.INFO,
            )
            .limit(1)
        ).scalar_subquery()

        discovered_addresses_cte = (
            select(
                InterfaceTable.c.id,
                StaticIPAddressTable.c.ip,
            )
            .select_from(InterfaceTable)
            .join(
                InterfaceIPAddressTable,
                InterfaceTable.c.id == InterfaceIPAddressTable.c.interface_id,
            )
            .join(
                StaticIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
            )
            .where(
                StaticIPAddressTable.c.alloc_type == IpAddressType.DISCOVERED,
                StaticIPAddressTable.c.ip.is_not(None),
            )
        ).cte("discovered_addresses")

        DiscoveredAddress = StaticIPAddressTable.alias("discovered_ip")
        DiscoveredInterfaceIPAddresses = InterfaceIPAddressTable.alias(
            "discovered_interface_ip"
        )
        dhcp_address_cte = (
            select(
                StaticIPAddressTable.c.id,
                DiscoveredAddress.c.ip,
            )
            .select_from(StaticIPAddressTable)
            .distinct(StaticIPAddressTable.c.id)
            .join(
                InterfaceIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
            )
            .join(
                DiscoveredInterfaceIPAddresses,
                DiscoveredInterfaceIPAddresses.c.interface_id
                == InterfaceIPAddressTable.c.interface_id,
            )
            .join(
                DiscoveredAddress,
                DiscoveredAddress.c.id
                == InterfaceIPAddressTable.c.staticipaddress_id,
            )
            .where(
                StaticIPAddressTable.c.alloc_type == IpAddressType.DHCP,
                DiscoveredAddress.c.alloc_type == IpAddressType.DISCOVERED,
                DiscoveredAddress.c.ip.is_not(None),
            )
            .order_by(StaticIPAddressTable.c.id, DiscoveredAddress.c.id.desc())
            .limit(1)  # django logic extracts only the first. Do the same here
        ).cte("dhcp_address")

        interface_addresses_cte = (
            select(
                InterfaceTable.c.id,
                case(
                    (
                        StaticIPAddressTable.c.alloc_type
                        == IpAddressType.DHCP,
                        dhcp_address_cte.c.ip,
                    ),
                    else_=StaticIPAddressTable.c.ip,
                ).label("ip"),
            )
            .select_from(InterfaceTable)
            .join(
                InterfaceIPAddressTable,
                InterfaceTable.c.id == InterfaceIPAddressTable.c.interface_id,
            )
            .join(
                StaticIPAddressTable,
                InterfaceIPAddressTable.c.staticipaddress_id
                == StaticIPAddressTable.c.id,
            )
            .join(
                dhcp_address_cte,
                dhcp_address_cte.c.id == StaticIPAddressTable.c.id,
                isouter=True,
            )
            .where(
                StaticIPAddressTable.c.ip.is_not(None),
                StaticIPAddressTable.c.alloc_type.in_(
                    (
                        IpAddressType.DHCP,
                        IpAddressType.AUTO,
                        IpAddressType.STICKY,
                        IpAddressType.USER_RESERVED,
                    )
                ),
            )
        ).cte("interface_addresses")

        ip_addresses_cte = (
            select(
                NodeTable.c.id,
                postgresql.array_agg(interface_addresses_cte.c.ip).label(
                    "ips"
                ),
                postgresql.array_agg(
                    interface_addresses_cte.c.id
                    == boot_interface_ip_cte.c.boot_interface_id
                ).label("is_boot_ips"),
            )
            .select_from(NodeTable)
            .join(interfaces_cte, interfaces_cte.c.node_id == NodeTable.c.id)
            .join(
                interface_addresses_cte,
                interface_addresses_cte.c.id == interfaces_cte.c.interface_id,
            )
            .join(
                boot_interface_ip_cte,
                boot_interface_ip_cte.c.id == NodeTable.c.id,
            )
            .group_by(NodeTable.c.id)
        ).cte("ip_addresses")
        discovered_machine_addresses_cte = (
            select(
                NodeTable.c.id,
                postgresql.array_agg(discovered_addresses_cte.c.ip).label(
                    "ips"
                ),
                postgresql.array_agg(
                    discovered_addresses_cte.c.id
                    == boot_interface_ip_cte.c.boot_interface_id
                ).label("is_boot_ips"),
            )
            .select_from(NodeTable)
            .join(interfaces_cte, interfaces_cte.c.node_id == NodeTable.c.id)
            .join(
                discovered_addresses_cte,
                discovered_addresses_cte.c.id == interfaces_cte.c.interface_id,
            )
            .join(
                boot_interface_ip_cte,
                boot_interface_ip_cte.c.id == NodeTable.c.id,
            )
            .group_by(NodeTable.c.id)
        ).cte("discovered_machine_ip_addresses")

        base_testing_status_cte = (
            select(
                ScriptSetTable.c.node_id,
                ScriptResultTable.c.script_name,
                ScriptResultTable.c.physical_blockdevice_id,
                ScriptResultTable.c.interface_id,
                ScriptResultTable.c.status,
                ScriptResultTable.c.suppressed,
                ScriptTable.c.hardware_type,
                ScriptSetTable.c.result_type,
            )
            .distinct(
                ScriptResultTable.c.script_name,
                ScriptResultTable.c.physical_blockdevice_id,
                ScriptResultTable.c.interface_id,
                ScriptSetTable.c.node_id,
            )
            .select_from(NodeTable)
            .join(ScriptSetTable, ScriptSetTable.c.node_id == NodeTable.c.id)
            .join(
                ScriptResultTable,
                ScriptResultTable.c.script_set_id == ScriptSetTable.c.id,
            )
            .join(
                ScriptTable, ScriptTable.c.id == ScriptResultTable.c.script_id
            )
            .where(
                ScriptSetTable.c.result_type == RESULT_TYPE.TESTING,
                ScriptResultTable.c.suppressed == False,  # noqa: E712
            )
            .order_by(
                ScriptResultTable.c.script_name,
                ScriptResultTable.c.physical_blockdevice_id,
                ScriptResultTable.c.interface_id,
                ScriptSetTable.c.node_id,
                desc(ScriptResultTable.c.id),
            )
        ).cte("base_testing_status")

        summary_testing_status_cte = (
            select(
                base_testing_status_cte.c.node_id,
                base_testing_status_cte.c.hardware_type,
                postgresql.array_agg(
                    func.distinct(base_testing_status_cte.c.status)
                ).label("statuses"),
            )
            .select_from(base_testing_status_cte)
            .group_by(
                base_testing_status_cte.c.node_id,
                base_testing_status_cte.c.hardware_type,
            )
        ).cte("summary_testing_status")

        testing_status_cte = (
            select(
                summary_testing_status_cte.c.node_id.label("id"),
                func.bool_or(
                    case(
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.RUNNING,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.APPLYING_NETCONF,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.INSTALLING,
                            True,
                        ),
                        else_=False,
                    )
                ).label("testing_status_combined_running"),
                func.bool_or(
                    case(
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.TIMEDOUT,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED_INSTALLING,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                            True,
                        ),
                        else_=False,
                    )
                ).label("testing_status_combined_failed"),
                func.bool_or(
                    case(
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.PENDING,
                            True,
                        ),
                        else_=False,
                    )
                ).label("testing_status_combined_pending"),
                func.bool_or(
                    case(
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.ABORTED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("testing_status_combined_aborted"),
                func.bool_or(
                    case(
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.DEGRADED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("testing_status_combined_degraded"),
                func.bool_or(
                    case(
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.PASSED,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.SKIPPED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("testing_status_combined_passed"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.STORAGE,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.RUNNING,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.APPLYING_NETCONF,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.INSTALLING,
                            True,
                        ),
                        else_=False,
                    )
                ).label("storage_test_status_combined_running"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.STORAGE,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.TIMEDOUT,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED_INSTALLING,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                            True,
                        ),
                        else_=False,
                    )
                ).label("storage_test_status_combined_failed"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.STORAGE,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.PENDING,
                            True,
                        ),
                        else_=False,
                    )
                ).label("storage_test_status_combined_pending"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.STORAGE,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.ABORTED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("storage_test_status_combined_aborted"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.STORAGE,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.DEGRADED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("storage_test_status_combined_degraded"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.STORAGE,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.PASSED,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.SKIPPED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("storage_test_status_combined_passed"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.NETWORK,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.RUNNING,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.APPLYING_NETCONF,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.INSTALLING,
                            True,
                        ),
                        else_=False,
                    )
                ).label("network_test_status_combined_running"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.NETWORK,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.TIMEDOUT,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED_INSTALLING,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                            True,
                        ),
                        else_=False,
                    )
                ).label("network_test_status_combined_failed"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.NETWORK,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.PENDING,
                            True,
                        ),
                        else_=False,
                    )
                ).label("network_test_status_combined_pending"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.NETWORK,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.ABORTED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("network_test_status_combined_aborted"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.NETWORK,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.DEGRADED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("network_test_status_combined_degraded"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.NETWORK,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.PASSED,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.SKIPPED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("network_test_status_combined_passed"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.MEMORY,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.RUNNING,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.APPLYING_NETCONF,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.INSTALLING,
                            True,
                        ),
                        else_=False,
                    )
                ).label("memory_test_status_combined_running"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.MEMORY,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.TIMEDOUT,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED_INSTALLING,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                            True,
                        ),
                        else_=False,
                    )
                ).label("memory_test_status_combined_failed"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.MEMORY,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.PENDING,
                            True,
                        ),
                        else_=False,
                    )
                ).label("memory_test_status_combined_pending"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.MEMORY,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.ABORTED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("memory_test_status_combined_aborted"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.MEMORY,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.DEGRADED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("memory_test_status_combined_degraded"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.MEMORY,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.PASSED,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.SKIPPED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("memory_test_status_combined_passed"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.CPU,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.RUNNING,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.APPLYING_NETCONF,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.INSTALLING,
                            True,
                        ),
                        else_=False,
                    )
                ).label("cpu_test_status_combined_running"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.CPU,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.TIMEDOUT,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED_INSTALLING,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
                            True,
                        ),
                        else_=False,
                    )
                ).label("cpu_test_status_combined_failed"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.CPU,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.PENDING,
                            True,
                        ),
                        else_=False,
                    )
                ).label("cpu_test_status_combined_pending"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.CPU,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.ABORTED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("cpu_test_status_combined_aborted"),
                func.bool_or(
                    case(
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == HARDWARE_TYPE.CPU,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.DEGRADED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("cpu_test_status_combined_degraded"),
                func.bool_or(
                    case(
                        (
                            summary_testing_status_cte.c.hardware_type
                            != HARDWARE_TYPE.CPU,
                            False,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.PASSED,
                            True,
                        ),
                        (
                            ColumnOperators.any_(
                                summary_testing_status_cte.c.statuses
                            )
                            == SCRIPT_STATUS.SKIPPED,
                            True,
                        ),
                        else_=False,
                    )
                ).label("cpu_test_status_combined_passed"),
            )
            .select_from(summary_testing_status_cte)
            .group_by(summary_testing_status_cte.c.node_id)
        ).cte("testing_status")

        tags_cte = (
            select(
                NodeTable.c.id,
                postgresql.array_agg(NodeTagTable.c.tag_id).label("tag_ids"),
            )
            .select_from(NodeTable)
            .join(NodeTagTable, NodeTagTable.c.node_id == NodeTable.c.id)
            .group_by(NodeTable.c.id)
        ).cte("machine_tags")

        PXEBootInterface = InterfaceTable.alias("pxe_boot_interface")
        pxe_mac_cte = (
            select(
                NodeTable.c.id,
                # Simply take just one
                func.min(
                    case(
                        (
                            NodeTable.c.boot_interface_id.isnot(None),
                            PXEBootInterface.c.mac_address,
                        ),
                        (
                            InterfaceTable.c.id.isnot(None),
                            InterfaceTable.c.mac_address,
                        ),
                        else_=None,
                    )
                ).label("pxe_mac"),
            )
            .select_from(NodeTable)
            .join(
                NodeConfigTable,
                NodeTable.c.current_config_id == NodeConfigTable.c.id,
                isouter=True,
            )
            .join(
                InterfaceTable,
                InterfaceTable.c.node_config_id == NodeConfigTable.c.id,
                isouter=True,
            )
            .join(
                PXEBootInterface,
                PXEBootInterface.c.id == NodeTable.c.boot_interface_id,
                isouter=True,
            )
            .group_by(NodeTable.c.id)
        ).cte("pxe_mac")

        MachineParent = NodeTable.alias("parent")
        BootVlan = VlanTable.alias("boot_vlan")
        BootInterface = InterfaceTable.alias("boot_interface")
        BootFabric = FabricTable.alias("boot_fabric")
        stmt = (
            select(
                NodeTable.c.id,
                NodeTable.c.system_id,
                NodeTable.c.hostname,
                NodeTable.c.description,
                DomainTable.c.id.label("domain_id"),
                DomainTable.c.name.label("domain_name"),
                ResourcePoolTable.c.id.label("pool_id"),
                ResourcePoolTable.c.name.label("pool_name"),
                func.coalesce(UserTable.c.username, "").label("owner"),
                MachineParent.c.system_id.label("parent"),
                NodeTable.c.error_description,
                ZoneTable.c.id.label("zone_id"),
                ZoneTable.c.name.label("zone_name"),
                NodeTable.c.cpu_count,
                func.round((NodeTable.c.memory / 1024), 1).label("memory"),
                NodeTable.c.power_state,
                NodeTable.c.locked,
                func.concat(
                    NodeTable.c.hostname, ".", DomainTable.c.name
                ).label("fqdn"),
                func.coalesce(tags_cte.c.tag_ids, []).label("tags"),
                func.coalesce(storage_query.c.disk_count, 0).label(
                    "physical_disk_count"
                ),
                func.coalesce(
                    func.round((storage_query.c.storage / (1000**3)), 1), 0
                ).label("storage"),
                NodeTable.c.architecture,
                NodeTable.c.osystem,
                NodeTable.c.distro_series,
                NodeTable.c.status.label("status_code"),
                NodeTable.c.ephemeral_deploy,
                func.coalesce(fabrics_cte.c.names, []).label("fabrics"),
                func.coalesce(spaces_cte.c.names, []).label("spaces"),
                func.coalesce(extra_macs_cte.c.extra_macs, []).label(
                    "extra_macs"
                ),
                func.coalesce(pxe_mac_cte.c.pxe_mac, "").label("pxe_mac"),
                BMCTable.c.power_type,
                case(
                    (
                        BMCTable.c.bmc_type == BmcType.POD,
                        BMCTable.c.id,
                    ),
                    else_=None,
                ).label("pod_id"),
                case(
                    (
                        BMCTable.c.bmc_type == BmcType.POD,
                        BMCTable.c.name,
                    ),
                    else_=None,
                ).label("pod_name"),
                status_message_subquery.label("status_message"),
                BootVlan.c.id.label("boot_vlan_id"),
                func.coalesce(BootVlan.c.name, "").label("boot_vlan_name"),
                BootVlan.c.fabric_id.label("boot_fabric_id"),
                BootFabric.c.name.label("boot_fabric_name"),
                case(
                    (
                        ip_addresses_cte.c.ips.is_(None),
                        func.coalesce(
                            discovered_machine_addresses_cte.c.ips, []
                        ),
                    ),
                    else_=func.coalesce(ip_addresses_cte.c.ips, []),
                ).label("ips"),
                case(
                    (
                        ip_addresses_cte.c.ips.is_(None),
                        func.coalesce(
                            discovered_machine_addresses_cte.c.is_boot_ips, []
                        ),
                    ),
                    else_=func.coalesce(ip_addresses_cte.c.is_boot_ips, []),
                ).label("is_boot_ips"),
                case(
                    (
                        testing_status_cte.c.testing_status_combined_running.is_(
                            True
                        ),
                        SCRIPT_STATUS.RUNNING,
                    ),
                    (
                        testing_status_cte.c.testing_status_combined_pending.is_(
                            True
                        ),
                        SCRIPT_STATUS.PENDING,
                    ),
                    (
                        testing_status_cte.c.testing_status_combined_failed.is_(
                            True
                        ),
                        SCRIPT_STATUS.FAILED,
                    ),
                    (
                        testing_status_cte.c.testing_status_combined_degraded.is_(
                            True
                        ),
                        SCRIPT_STATUS.DEGRADED,
                    ),
                    (
                        testing_status_cte.c.testing_status_combined_passed.is_(
                            True
                        ),
                        SCRIPT_STATUS.PASSED,
                    ),
                    else_=-1,
                ).label("testing_status_combined"),
                case(
                    (
                        testing_status_cte.c.storage_test_status_combined_running.is_(
                            True
                        ),
                        SCRIPT_STATUS.RUNNING,
                    ),
                    (
                        testing_status_cte.c.storage_test_status_combined_pending.is_(
                            True
                        ),
                        SCRIPT_STATUS.PENDING,
                    ),
                    (
                        testing_status_cte.c.storage_test_status_combined_failed.is_(
                            True
                        ),
                        SCRIPT_STATUS.FAILED,
                    ),
                    (
                        testing_status_cte.c.storage_test_status_combined_degraded.is_(
                            True
                        ),
                        SCRIPT_STATUS.DEGRADED,
                    ),
                    (
                        testing_status_cte.c.storage_test_status_combined_passed.is_(
                            True
                        ),
                        SCRIPT_STATUS.PASSED,
                    ),
                    else_=-1,
                ).label("storage_test_status_combined"),
                case(
                    (
                        testing_status_cte.c.network_test_status_combined_running.is_(
                            True
                        ),
                        SCRIPT_STATUS.RUNNING,
                    ),
                    (
                        testing_status_cte.c.network_test_status_combined_pending.is_(
                            True
                        ),
                        SCRIPT_STATUS.PENDING,
                    ),
                    (
                        testing_status_cte.c.network_test_status_combined_failed.is_(
                            True
                        ),
                        SCRIPT_STATUS.FAILED,
                    ),
                    (
                        testing_status_cte.c.network_test_status_combined_degraded.is_(
                            True
                        ),
                        SCRIPT_STATUS.DEGRADED,
                    ),
                    (
                        testing_status_cte.c.network_test_status_combined_passed.is_(
                            True
                        ),
                        SCRIPT_STATUS.PASSED,
                    ),
                    else_=-1,
                ).label("network_test_status_combined"),
                case(
                    (
                        testing_status_cte.c.cpu_test_status_combined_running.is_(
                            True
                        ),
                        SCRIPT_STATUS.RUNNING,
                    ),
                    (
                        testing_status_cte.c.cpu_test_status_combined_pending.is_(
                            True
                        ),
                        SCRIPT_STATUS.PENDING,
                    ),
                    (
                        testing_status_cte.c.cpu_test_status_combined_failed.is_(
                            True
                        ),
                        SCRIPT_STATUS.FAILED,
                    ),
                    (
                        testing_status_cte.c.cpu_test_status_combined_degraded.is_(
                            True
                        ),
                        SCRIPT_STATUS.DEGRADED,
                    ),
                    (
                        testing_status_cte.c.cpu_test_status_combined_passed.is_(
                            True
                        ),
                        SCRIPT_STATUS.PASSED,
                    ),
                    else_=-1,
                ).label("cpu_test_status_combined"),
                case(
                    (
                        testing_status_cte.c.memory_test_status_combined_running.is_(
                            True
                        ),
                        SCRIPT_STATUS.RUNNING,
                    ),
                    (
                        testing_status_cte.c.memory_test_status_combined_pending.is_(
                            True
                        ),
                        SCRIPT_STATUS.PENDING,
                    ),
                    (
                        testing_status_cte.c.memory_test_status_combined_failed.is_(
                            True
                        ),
                        SCRIPT_STATUS.FAILED,
                    ),
                    (
                        testing_status_cte.c.memory_test_status_combined_degraded.is_(
                            True
                        ),
                        SCRIPT_STATUS.DEGRADED,
                    ),
                    (
                        testing_status_cte.c.memory_test_status_combined_passed.is_(
                            True
                        ),
                        SCRIPT_STATUS.PASSED,
                    ),
                    else_=-1,
                ).label("memory_test_status_combined"),
                NodeTable.c.is_dpu,
            )
            .select_from(NodeTable)
            .join(
                DomainTable,
                DomainTable.c.id == NodeTable.c.domain_id,
                isouter=True,
            )
            .join(
                UserTable, UserTable.c.id == NodeTable.c.owner_id, isouter=True
            )
            .join(
                ResourcePoolTable,
                ResourcePoolTable.c.id == NodeTable.c.pool_id,
                isouter=True,
            )
            .join(
                ZoneTable, ZoneTable.c.id == NodeTable.c.zone_id, isouter=True
            )
            .join(
                storage_query,
                storage_query.c.id == NodeTable.c.id,
                isouter=True,
            )
            .join(
                fabrics_cte,
                fabrics_cte.c.node_id == NodeTable.c.id,
                isouter=True,
            )
            .join(
                spaces_cte,
                spaces_cte.c.node_id == NodeTable.c.id,
                isouter=True,
            )
            .join(
                MachineParent,
                MachineParent.c.id == NodeTable.c.parent_id,
                isouter=True,
            )
            .join(
                extra_macs_cte,
                extra_macs_cte.c.id == NodeTable.c.id,
                isouter=True,
            )
            .join(
                pxe_mac_cte,
                pxe_mac_cte.c.id == NodeTable.c.id,
                isouter=True,
            )
            .join(
                BootInterface,
                BootInterface.c.id == NodeTable.c.boot_interface_id,
                isouter=True,
            )
            .join(BMCTable, BMCTable.c.id == NodeTable.c.bmc_id, isouter=True)
            .join(
                BootVlan,
                BootVlan.c.id == BootInterface.c.vlan_id,
                isouter=True,
            )
            .join(
                BootFabric,
                BootFabric.c.id == BootVlan.c.fabric_id,
                isouter=True,
            )
            .join(
                ip_addresses_cte,
                ip_addresses_cte.c.id == NodeTable.c.id,
                isouter=True,
            )
            .join(
                discovered_machine_addresses_cte,
                discovered_machine_addresses_cte.c.id == NodeTable.c.id,
                isouter=True,
            )
            .join(
                testing_status_cte,
                testing_status_cte.c.id == NodeTable.c.id,
                isouter=True,
            )
            .join(
                tags_cte,
                tags_cte.c.id == NodeTable.c.id,
                isouter=True,
            )
            .where(NodeTable.c.id.in_(ids))
        )
        return stmt
