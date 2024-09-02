# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import desc, select, Select
from sqlalchemy.sql.operators import eq, le

from maasapiserver.v3.db.base import BaseRepository, CreateOrUpdateResource
from maasservicelayer.db.filters import FilterQuery
from maasservicelayer.db.tables import SpaceTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.spaces import Space


class SpacesRepository(BaseRepository[Space]):
    async def create(self, resource: CreateOrUpdateResource) -> Space:
        raise NotImplementedError()

    async def find_by_id(self, id: int) -> Space | None:
        stmt = self._select_all_statement().filter(eq(SpaceTable.c.id, id))

        result = await self.connection.execute(stmt)
        space = result.first()
        if not space:
            return None
        return Space(**space._asdict())

    async def find_by_name(self, name: str) -> Space | None:
        raise NotImplementedError()

    async def list(
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[Space]:
        # TODO: use the query for the filters
        stmt = (
            self._select_all_statement()
            .order_by(desc(SpaceTable.c.id))
            .limit(size + 1)  # Retrieve one more element to get the next token
        )
        if token is not None:
            stmt = stmt.where(le(SpaceTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id
        return ListResult[Space](
            items=[Space(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def update(self, id: int, resource: CreateOrUpdateResource) -> Space:
        raise NotImplementedError()

    async def delete(self, id: int) -> None:
        raise NotImplementedError()

    def _select_all_statement(self) -> Select[Any]:
        return select(
            SpaceTable.c.id,
            SpaceTable.c.created,
            SpaceTable.c.updated,
            SpaceTable.c.name,
            SpaceTable.c.description,
        ).select_from(SpaceTable)
