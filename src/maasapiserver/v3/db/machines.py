from typing import Any

from sqlalchemy import desc, select, Select
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db.tables import (
    BMCTable,
    DomainTable,
    NodeTable,
    UserTable,
)
from maasapiserver.v3.api.models.requests.machines import MachineRequest
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.machines import Machine
from maasserver.enum import NODE_TYPE


class MachinesRepository(BaseRepository[Machine, MachineRequest]):
    async def create(self, request: MachineRequest) -> Machine:
        raise Exception("Not implemented yet.")

    async def find_by_id(self, id: int) -> Machine | None:
        raise Exception("Not implemented yet.")

    async def list(
        self, pagination_params: PaginationParams
    ) -> ListResult[Machine]:
        total_stmt = (
            select(count())
            .select_from(NodeTable)
            .where(eq(NodeTable.c.node_type, NODE_TYPE.MACHINE))
        )
        total = (await self.connection.execute(total_stmt)).scalar()

        stmt = (
            self._select_all_statement()
            .order_by(desc(NodeTable.c.id))
            .offset((pagination_params.page - 1) * pagination_params.size)
            .limit(pagination_params.size)
        )

        result = await self.connection.execute(stmt)
        return ListResult[Machine](
            items=[Machine(**row._asdict()) for row in result.all()],
            total=total,
        )

    async def update(self, resource: Machine) -> Machine:
        raise Exception("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise Exception("Not implemented yet.")

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
