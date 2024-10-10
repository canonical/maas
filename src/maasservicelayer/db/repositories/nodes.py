#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import ColumnElement, Select, select, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.sql.operators import eq

from maascommon.enums.node import NodeStatus
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
    CreateOrUpdateResourceBuilder,
)
from maasservicelayer.db.tables import BMCTable, NodeTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.nodes import Node


class NodeCreateOrUpdateResourceBuilder(CreateOrUpdateResourceBuilder):
    def with_status(
        self, status: NodeStatus
    ) -> "NodeCreateOrUpdateResourceBuilder":
        self._request.set_value(NodeTable.c.status.name, status)
        return self


class NodesRepository(BaseRepository[Node]):
    async def create(self, resource: CreateOrUpdateResource) -> Node:
        raise NotImplementedError("Not implemented yet.")

    async def find_by_id(self, id: int) -> Node | None:
        raise NotImplementedError("Not implemented yet.")

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[Node]:
        raise NotImplementedError("Not implemented yet.")

    async def update(self, id: int, resource: CreateOrUpdateResource) -> Node:
        return await self._update(eq(NodeTable.c.id, id), resource)

    async def update_by_system_id(
        self, system_id: str, resource: CreateOrUpdateResource
    ) -> Node:
        return await self._update(
            eq(NodeTable.c.system_id, system_id), resource
        )

    async def _update(
        self, clause: ColumnElement, resource: CreateOrUpdateResource
    ) -> Node:
        stmt = (
            update(NodeTable)
            .where(clause)
            .returning(NodeTable)
            .values(**resource.get_values())
        )
        try:
            new_node = (await self.connection.execute(stmt)).one()
        except IntegrityError:
            self._raise_already_existing_exception()
        except NoResultFound:
            self._raise_not_found_exception()
        return Node(**new_node._asdict())

    async def delete(self, id: int) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        stmt = (
            update(NodeTable)
            .where(eq(NodeTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.connection.execute(stmt)

    async def get_node_bmc(self, system_id: str) -> Bmc | None:
        stmt = self._bmc_select_all_statement().where(
            eq(NodeTable.c.system_id, system_id)
        )

        result = (await self.connection.execute(stmt)).one()
        return Bmc(**result._asdict())

    async def move_bmcs_to_zone(
        self, old_zone_id: int, new_zone_id: int
    ) -> None:
        stmt = (
            update(BMCTable)
            .where(eq(BMCTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.connection.execute(stmt)

    def _bmc_select_all_statement(self) -> Select[Any]:
        # TODO: add other fields
        return (
            select(
                BMCTable.c.id,
                BMCTable.c.created,
                BMCTable.c.updated,
                BMCTable.c.power_type,
                BMCTable.c.power_parameters,
            )
            .select_from(BMCTable)
            .join(NodeTable, eq(NodeTable.c.bmc_id, BMCTable.c.id))
        )
