# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import desc, select
from sqlalchemy.sql.operators import eq, le

from maasapiserver.common.db.filters import FilterQuery
from maasapiserver.common.db.tables import VlanTable
from maasapiserver.v3.db.base import BaseRepository, CreateOrUpdateResource
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.vlans import Vlan


class VlansRepository(BaseRepository[Vlan]):
    async def create(self, resource: CreateOrUpdateResource) -> Vlan:
        raise NotImplementedError()

    async def find_by_id(self, id: int) -> Vlan | None:
        stmt = select("*").filter(eq(VlanTable.c.id, id))

        result = await self.connection.execute(stmt)
        vlan = result.first()
        if not vlan:
            return None
        return Vlan(**vlan._asdict())

    async def find_by_name(self, name: str) -> Vlan | None:
        raise NotImplementedError()

    async def list(
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[Vlan]:
        # TODO: use the query for the filters
        stmt = (
            select("*")
            .select_from(VlanTable)
            .order_by(desc(VlanTable.c.id))
            .limit(size + 1)  # Retrieve one more element to get the next token
        )
        if token is not None:
            stmt = stmt.where(le(VlanTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id
        return ListResult[Vlan](
            items=[Vlan(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def update(self, id: int, resource: CreateOrUpdateResource) -> Vlan:
        raise NotImplementedError()

    async def delete(self, id: int) -> None:
        raise NotImplementedError()
