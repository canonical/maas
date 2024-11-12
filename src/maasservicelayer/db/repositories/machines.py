#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Type

from sqlalchemy import and_, desc, select, Select, Table
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.operators import eq, le

from maascommon.enums.node import NodeDeviceBus, NodeStatus, NodeTypeEnum
from maascommon.workflows.msm import MachinesCountByStatus
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    BMCTable,
    DomainTable,
    NodeConfigTable,
    NodeDeviceTable,
    NodeTable,
    UserTable,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.machines import Machine, PciDevice, UsbDevice


class MachineClauseFactory(ClauseFactory):
    @classmethod
    def with_owner(cls, owner: str | None) -> Clause:
        return Clause(condition=eq(UserTable.c.username, owner))

    @classmethod
    def with_resource_pool_ids(cls, rp_ids: set[int] | None) -> Clause:
        if rp_ids is None:
            rp_ids = set()
        return Clause(condition=NodeTable.c.pool_id.in_(rp_ids))


class MachinesRepository(BaseRepository[Machine]):

    def get_repository_table(self) -> Table:
        return NodeTable

    def get_model_factory(self) -> Type[Machine]:
        return Machine

    def select_all_statement(self) -> Select[Any]:
        return (
            select(
                NodeTable.c.id,
                NodeTable.c.system_id,
                NodeTable.c.created,
                NodeTable.c.updated,
                func.coalesce(UserTable.c.username, "").label("owner"),
                NodeTable.c.description,
                NodeTable.c.cpu_speed,
                NodeTable.c.memory,
                NodeTable.c.osystem,
                NodeTable.c.architecture,
                NodeTable.c.distro_series,
                NodeTable.c.hwe_kernel,
                NodeTable.c.locked,
                NodeTable.c.cpu_count,
                NodeTable.c.status,
                NodeTable.c.hostname,
                BMCTable.c.power_type,
                func.concat(
                    NodeTable.c.hostname, ".", DomainTable.c.name
                ).label("fqdn"),
            )
            .select_from(NodeTable)
            .join(
                DomainTable,
                eq(DomainTable.c.id, NodeTable.c.domain_id),
                isouter=True,
            )
            .join(
                UserTable,
                eq(UserTable.c.id, NodeTable.c.owner_id),
                isouter=True,
            )
            .join(
                BMCTable, eq(BMCTable.c.id, NodeTable.c.bmc_id), isouter=True
            )
            .where(eq(NodeTable.c.node_type, NodeTypeEnum.MACHINE))
        )

    async def list_machine_usb_devices(
        self, system_id: str, token: str | None, size: int
    ) -> ListResult[UsbDevice]:
        stmt = (
            self._list_devices_statement(system_id)
            .order_by(desc(NodeDeviceTable.c.id))
            .where(eq(NodeDeviceTable.c.bus, NodeDeviceBus.USB))
            .limit(size + 1)
        )
        if token is not None:
            stmt = stmt.where(le(NodeDeviceTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id

        return ListResult[UsbDevice](
            items=[UsbDevice(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def list_machine_pci_devices(
        self, system_id: str, token: str | None, size: int
    ) -> ListResult[PciDevice]:
        stmt = (
            self._list_devices_statement(system_id)
            .order_by(desc(NodeDeviceTable.c.id))
            .where(eq(NodeDeviceTable.c.bus, NodeDeviceBus.PCIE))
            .limit(size + 1)
        )
        if token is not None:
            stmt = stmt.where(le(NodeDeviceTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id

        return ListResult[PciDevice](
            items=[PciDevice(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def count_machines_by_statuses(self) -> MachinesCountByStatus:
        stmt = (
            select(NodeTable.c.status, count(NodeTable.c.id).label("total"))
            .select_from(NodeTable)
            .where(eq(NodeTable.c.node_type, NodeTypeEnum.MACHINE))
            .group_by(NodeTable.c.status)
        )
        result = (await self.connection.execute(stmt)).all()
        machines_count = MachinesCountByStatus()
        for row in result:
            match row.status:
                case NodeStatus.ALLOCATED:
                    machines_count.allocated += row.total
                case NodeStatus.DEPLOYED:
                    machines_count.deployed += row.total
                case NodeStatus.READY:
                    machines_count.ready += row.total
                case (
                    NodeStatus.FAILED_COMMISSIONING
                    | NodeStatus.FAILED_DEPLOYMENT
                    | NodeStatus.FAILED_DISK_ERASING
                    | NodeStatus.FAILED_ENTERING_RESCUE_MODE
                    | NodeStatus.FAILED_EXITING_RESCUE_MODE
                    | NodeStatus.FAILED_RELEASING
                    | NodeStatus.FAILED_TESTING
                ):
                    machines_count.error += row.total
                case _:
                    machines_count.other += row.total
        return machines_count

    def _list_devices_statement(self, system_id: str) -> Select[Any]:
        return (
            select(
                NodeDeviceTable.c.id,
                NodeDeviceTable.c.created,
                NodeDeviceTable.c.updated,
                NodeDeviceTable.c.bus,
                NodeDeviceTable.c.hardware_type,
                NodeDeviceTable.c.vendor_id,
                NodeDeviceTable.c.product_id,
                NodeDeviceTable.c.vendor_name,
                NodeDeviceTable.c.product_name,
                NodeDeviceTable.c.commissioning_driver,
                NodeDeviceTable.c.bus_number,
                NodeDeviceTable.c.device_number,
                NodeDeviceTable.c.pci_address,
                NodeDeviceTable.c.numa_node_id,
                NodeDeviceTable.c.physical_blockdevice_id,
                NodeDeviceTable.c.physical_interface_id,
                NodeDeviceTable.c.node_config_id,
            )
            .select_from(NodeDeviceTable)
            .join(
                NodeConfigTable,
                eq(NodeConfigTable.c.id, NodeDeviceTable.c.node_config_id),
            )
            .join(NodeTable, eq(NodeTable.c.id, NodeConfigTable.c.node_id))
            .where(
                and_(
                    eq(NodeTable.c.system_id, system_id),
                    eq(NodeConfigTable.c.id, NodeTable.c.current_config_id),
                )
            )
        )
