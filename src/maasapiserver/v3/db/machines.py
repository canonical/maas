from typing import Any

from sqlalchemy import and_, desc, select, Select
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.operators import eq, le

from maasapiserver.common.db.filters import FilterQuery
from maasapiserver.common.db.tables import (
    BMCTable,
    DomainTable,
    NodeConfigTable,
    NodeDeviceTable,
    NodeTable,
    UserTable,
)
from maasapiserver.v3.db.base import BaseRepository, CreateOrUpdateResource
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.machines import Machine, UsbDevice
from maasserver.enum import NODE_DEVICE_BUS, NODE_TYPE


class MachinesRepository(BaseRepository[Machine]):
    async def create(self, resource: CreateOrUpdateResource) -> Machine:
        raise NotImplementedError("Not implemented yet.")

    async def find_by_id(self, id: int) -> Machine | None:
        raise NotImplementedError("Not implemented yet.")

    async def list(
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[Machine]:
        # TODO: use the query for the filters
        stmt = (
            self._select_all_statement()
            .order_by(desc(NodeTable.c.id))
            .limit(size + 1)
        )
        if token is not None:
            stmt = stmt.where(le(NodeTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id
        return ListResult[Machine](
            items=[Machine(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> Machine:
        raise NotImplementedError("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def list_machine_usb_devices(
        self, system_id: str, token: str | None, size: int
    ) -> ListResult[UsbDevice]:
        stmt = (
            self._list_devices_statement(system_id)
            .order_by(desc(NodeDeviceTable.c.id))
            .where(eq(NodeDeviceTable.c.bus, NODE_DEVICE_BUS.USB))
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

    def _select_all_statement(self) -> Select[Any]:
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
            .where(eq(NodeTable.c.node_type, NODE_TYPE.MACHINE))
        )
