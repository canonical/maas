# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import desc, select, Select
from sqlalchemy.sql.operators import eq, le

from maasapiserver.v3.db.base import BaseRepository, CreateOrUpdateResource
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.fabrics import Fabric
from maasservicelayer.db.filters import FilterQuery
from maasservicelayer.db.tables import FabricTable


class FabricsRepository(BaseRepository[Fabric]):
    async def create(self, resource: CreateOrUpdateResource) -> Fabric:
        raise NotImplementedError()

    async def find_by_id(self, id: int) -> Fabric | None:
        stmt = self._select_all_statement().filter(eq(FabricTable.c.id, id))

        result = await self.connection.execute(stmt)
        fabric = result.first()
        if not fabric:
            return None
        return Fabric(**fabric._asdict())

    async def find_by_name(self, name: str) -> Fabric | None:
        raise NotImplementedError()

    async def list(
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[Fabric]:
        # TODO: use the query for the filters
        stmt = (
            self._select_all_statement()
            .order_by(desc(FabricTable.c.id))
            .limit(size + 1)  # Retrieve one more element to get the next token
        )
        if token is not None:
            stmt = stmt.where(le(FabricTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id
        return ListResult[Fabric](
            items=[Fabric(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> Fabric:
        raise NotImplementedError()

    async def delete(self, id: int) -> None:
        raise NotImplementedError()

    def _select_all_statement(self) -> Select[Any]:
        return select(
            FabricTable.c.id,
            FabricTable.c.created,
            FabricTable.c.updated,
            FabricTable.c.name,
            FabricTable.c.description,
            FabricTable.c.class_type,
        ).select_from(FabricTable)
