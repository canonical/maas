#  Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Type

from sqlalchemy import and_, desc, Select, select, Table
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.operators import eq

from maascommon.enums.node import NodeDeviceBus, NodeStatus, NodeTypeEnum
from maascommon.workflows.msm import MachinesCountByStatus
from maasservicelayer.db.filters import SQLQuerySpec
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.mappers.machines import MachineDomainDataMapper
from maasservicelayer.db.repositories.nodes import AbstractNodesRepository
from maasservicelayer.db.tables import (
    NodeConfigTable,
    NodeDeviceTable,
    NodeTable,
)
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.machines import Machine, PciDevice, UsbDevice


class MachinesRepository(AbstractNodesRepository[Machine]):
    usb_device_mapper = DefaultDomainDataMapper[UsbDevice](
        UsbDevice, NodeDeviceTable
    )
    pci_device_mapper = DefaultDomainDataMapper[PciDevice](
        PciDevice, NodeDeviceTable
    )

    def get_repository_table(self) -> Table:
        return NodeTable

    def get_model_factory(self) -> Type[Machine]:
        return Machine

    def get_mapper(self) -> MachineDomainDataMapper:
        return MachineDomainDataMapper(
            self.get_model_factory(), self.get_repository_table()
        )

    async def list(
        self, page: int, size: int, query: QuerySpec | None = None
    ) -> ListResult[Machine]:
        # Override the default implementation because we have to specialize the `total_stmt` query. If we realise this is a
        # common use case, we might think about an abstraction at BaseRepository level.
        translated = self._translate(query) if query is not None else None
        total_stmt = (
            select(count())
            .select_from(NodeTable)
            .where(eq(NodeTable.c.node_type, NodeTypeEnum.MACHINE))
        )
        if translated is not None:
            total_stmt = SQLQuerySpec(where=translated.where).enrich_stmt(
                total_stmt
            )
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = (
            self.select_all_statement()
            .order_by(desc(self.get_repository_table().c.id))
            .offset((page - 1) * size)
            .limit(size)
        )
        if translated is not None:
            stmt = translated.enrich_stmt(stmt)
        result = (await self.execute_stmt(stmt)).all()
        return ListResult[Machine](
            items=[self.mapper.to_domain(row._mapping) for row in result],
            total=total,
        )

    async def list_machine_usb_devices(
        self, system_id: str, page: int, size: int
    ) -> ListResult[UsbDevice]:
        total_stmt = select(count()).select_from(
            self._list_devices_statement(system_id)
            .where(eq(NodeDeviceTable.c.bus, NodeDeviceBus.USB))
            .subquery()
        )
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = (
            self._list_devices_statement(system_id)
            .order_by(desc(NodeDeviceTable.c.id))
            .where(eq(NodeDeviceTable.c.bus, NodeDeviceBus.USB))
            .offset((page - 1) * size)
            .limit(size)
        )

        result = (await self.execute_stmt(stmt)).all()

        return ListResult[UsbDevice](
            items=[
                self.usb_device_mapper.to_domain(row._mapping)
                for row in result
            ],
            total=total,
        )

    async def list_machine_pci_devices(
        self, system_id: str, page: int, size: int
    ) -> ListResult[PciDevice]:
        total_stmt = select(count()).select_from(
            self._list_devices_statement(system_id)
            .where(eq(NodeDeviceTable.c.bus, NodeDeviceBus.PCIE))
            .subquery()
        )
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = (
            self._list_devices_statement(system_id)
            .order_by(desc(NodeDeviceTable.c.id))
            .where(eq(NodeDeviceTable.c.bus, NodeDeviceBus.PCIE))
            .offset((page - 1) * size)
            .limit(size)
        )

        result = (await self.execute_stmt(stmt)).all()

        return ListResult[PciDevice](
            items=[
                self.pci_device_mapper.to_domain(row._mapping)
                for row in result
            ],
            total=total,
        )

    async def count_machines_by_statuses(self) -> MachinesCountByStatus:
        stmt = (
            select(NodeTable.c.status, count(NodeTable.c.id).label("total"))
            .select_from(NodeTable)
            .where(eq(NodeTable.c.node_type, NodeTypeEnum.MACHINE))
            .group_by(NodeTable.c.status)
        )
        result = (await self.execute_stmt(stmt)).all()
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
