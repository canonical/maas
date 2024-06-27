# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import desc, select, Select
from sqlalchemy.sql.operators import le

from maasapiserver.common.db.tables import SpaceTable
from maasapiserver.v3.api.models.requests.spaces import SpaceRequest
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.spaces import Space


class SpacesRepository(BaseRepository[Space, SpaceRequest]):
    async def create(self, request: SpaceRequest) -> Space:
        raise NotImplementedError()

    async def find_by_id(self, id: int) -> Space | None:
        raise NotImplementedError()

    async def find_by_name(self, name: str) -> Space | None:
        raise NotImplementedError()

    async def list(self, token: str | None, size: int) -> ListResult[Space]:
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

    async def update(self, resource: Space) -> Space:
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
