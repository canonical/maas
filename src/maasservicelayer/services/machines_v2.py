# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel

from maascommon.enums.node import SimplifiedNodeStatusEnum
from maasserver.enum import (
    NODE_STATUS_CHOICES_DICT,
    SIMPLIFIED_NODE_STATUSES_MAP_REVERSED,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.machines_v2 import MachinesV2Repository
from maasservicelayer.filters.nodes import NodeFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.machine_details import MachineRecord
from maasservicelayer.services.base import Service


# Requests
class MachineRequest(BaseModel):
    id: int
    actions: list[str]
    permissions: list[str]


class MachineListGroupRequest(BaseModel):
    name: str | None = None
    value: str | None = None
    count: int | None = None
    collapsed: bool | None = None
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
    status: int | None = None
    pending: int | None = None
    running: int | None = None
    passed: int | None = None
    failed: int | None = None


class Vlan(BaseModel):
    id: int | None = None
    name: str | None = None
    fabric_id: int | None = None
    fabric_name: str | None = None


class IPAddress(BaseModel):
    ip: str | None = None
    is_boot: bool | None = None


class Machine(BaseModel):
    # maasui/src/src/app/store/machine/types/base.ts

    id: int
    system_id: str
    hostname: str
    description: str
    pool: ModelRef
    domain: ModelRef
    owner: str
    parent: str | None = None
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
    tags: list[int] | None = None
    physical_disk_count: int | None = None
    storage: float | None = None
    testing_status: TestStatus | None = None
    architecture: str
    osystem: str
    distro_series: str
    status: str
    status_code: int
    simple_status: str
    ephemeral_deploy: bool
    fabrics: list[str] | None = None
    spaces: list[str] | None = None
    extra_macs: list[str] | None = None
    status_message: str | None = None
    pxe_mac: str | None = None
    vlan: Vlan | None = None
    power_type: str | None = None
    ip_addresses: list[IPAddress] | None = None
    cpu_test_status: TestStatus | None = None
    memory_test_status: TestStatus | None = None
    network_test_status: TestStatus | None = None
    storage_test_status: TestStatus | None = None
    is_dpu: bool


# Responses
class MachineListGroupResponse(BaseModel):
    name: str | None = None
    value: str | None = None
    count: int | None = None
    collapsed: bool | None = None
    items: list[Machine] | None = None


class MachineListResponse(BaseModel):
    count: int
    cur_page: int
    num_pages: int
    groups: list[MachineListGroupResponse] | None = None


class MachinesV2Service(Service):
    """
    TL;DR DO NOT USE THIS!

    This service was part of the first iteration of the maasapiserver. maasserver used to make a POST query to the apiserver to
    retrieve the machine listing. After that initial iteration, we decided to implement the v3 api and we integrated the
    service layer with maasserver. For this reason, we moved that logic to the service layer so that the websocket handlers can call this method directly.
    This service MUST be removed when the websocket handler for the machine list is removed - do not use this anymore!
    """

    def __init__(self, context: Context):
        super().__init__(context)
        self.repository = MachinesV2Repository(context)

    async def list(self, request: MachineListRequest) -> MachineListResponse:
        ids = []
        for group in request.groups:
            ids += list(map(lambda x: x.id, group.items))

        records = await self.repository.get_many(
            QuerySpec(where=NodeFilters.with_ids(ids))
        )

        machines = {}
        for record in records:
            machine = self._build_node(record)
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

    def _patch_machine(
        self, machine: Machine, actions: list[str], permissions: list[str]
    ) -> Machine:
        machine.actions = actions
        machine.permissions = permissions
        return machine

    def _build_node(self, record: MachineRecord) -> Machine:
        vlan = None
        if (
            record.boot_vlan_id
            or record.boot_vlan_name
            or record.boot_fabric_id
            or record.boot_fabric_name
        ):
            vlan = Vlan(
                id=record.boot_vlan_id,
                name=record.boot_vlan_name,
                fabric_id=record.boot_fabric_id,
                fabric_name=record.boot_fabric_name,
            )

        ip_addresses: list[IPAddress] | None = []
        if record.ips and record.is_boot_ips:
            for i in range(len(record.ips)):
                ip_addresses.append(
                    IPAddress(
                        ip=record.ips[i],
                        is_boot=record.is_boot_ips[i],
                    )
                )
        power_type = record.power_type
        if not record.pxe_mac:
            ip_addresses = None
            power_type = None

        machine = Machine.model_validate(
            {
                "id": record.id,
                "system_id": record.system_id,
                "hostname": record.hostname,
                "description": record.description,
                "pool": ModelRef.model_validate(
                    {"id": record.pool_id, "name": record.pool_name}
                ),
                "domain": ModelRef.model_validate(
                    {"id": record.domain_id, "name": record.domain_name}
                ),
                "owner": record.owner,
                "parent": record.parent,
                "error_description": record.error_description,
                "zone": ModelRef.model_validate(
                    {"id": record.zone_id, "name": record.zone_name}
                ),
                "cpu_count": record.cpu_count,
                "memory": int(record.memory),
                "power_state": record.power_state,
                "locked": record.locked,
                "permissions": [],
                "fqdn": record.fqdn,
                "actions": [],
                # maasserver/websockets/handlers/node.py:103
                "link_type": "machine",
                "tags": record.tags,
                "physical_disk_count": record.physical_disk_count,
                "storage": record.storage,
                "testing_status": TestStatus(
                    status=record.testing_status_combined,
                    pending=-1,
                    running=-1,
                    passed=-1,
                    failed=-1,
                ),
                "architecture": record.architecture,
                "osystem": record.osystem,
                "distro_series": record.distro_series,
                "status": NODE_STATUS_CHOICES_DICT[record.status_code],
                "status_code": record.status_code,
                "simple_status": SIMPLIFIED_NODE_STATUSES_MAP_REVERSED.get(
                    record.status_code, SimplifiedNodeStatusEnum.OTHER.value
                ),
                "ephemeral_deploy": record.ephemeral_deploy,
                "fabrics": record.fabrics,
                "spaces": record.spaces,
                "extra_macs": record.extra_macs,
                "status_message": record.status_message,
                "pxe_mac": record.pxe_mac,
                "vlan": vlan,
                "power_type": power_type,
                "ip_addresses": ip_addresses,
                "cpu_test_status": TestStatus(
                    status=record.cpu_test_status_combined,
                    pending=-1,
                    running=-1,
                    passed=-1,
                    failed=-1,
                ),
                "memory_test_status": TestStatus(
                    status=record.memory_test_status_combined,
                    pending=-1,
                    running=-1,
                    passed=-1,
                    failed=-1,
                ),
                "network_test_status": TestStatus(
                    status=record.network_test_status_combined,
                    pending=-1,
                    running=-1,
                    passed=-1,
                    failed=-1,
                ),
                "storage_test_status": TestStatus(
                    status=record.storage_test_status_combined,
                    pending=-1,
                    running=-1,
                    passed=-1,
                    failed=-1,
                ),
                "is_dpu": record.is_dpu,
            }
        )
        return machine
