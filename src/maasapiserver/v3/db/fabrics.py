# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import desc, select, Select
from sqlalchemy.sql.operators import le

from maasapiserver.common.db.tables import FabricTable
from maasapiserver.v3.api.models.requests.fabrics import FabricRequest
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.fabrics import Fabric


class FabricsRepository(BaseRepository[Fabric, FabricRequest]):
    async def create(self, request: FabricRequest) -> Fabric:
        raise NotImplementedError()

    async def find_by_id(self, id: int) -> Fabric | None:
        raise NotImplementedError()

    async def find_by_name(self, name: str) -> Fabric | None:
        raise NotImplementedError()

    async def list(
        self, pagination_params: PaginationParams
    ) -> ListResult[Fabric]:
        raise Exception("Not implemented. Use the token based pagination.")

    async def list_with_token(
        self, token: str | None, size: int
    ) -> ListResult[Fabric]:
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

    async def update(self, resource: Fabric) -> Fabric:
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
