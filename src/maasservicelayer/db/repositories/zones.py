#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import delete, desc, insert, select, Select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.operators import eq, le

from maasservicelayer.db.filters import FilterQuery, FilterQueryBuilder
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
    CreateOrUpdateResourceBuilder,
)
from maasservicelayer.db.tables import DefaultResourceTable, ZoneTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.zones import Zone


class ZoneCreateOrUpdateResourceBuilder(CreateOrUpdateResourceBuilder):
    def with_name(self, value: str) -> "ZoneCreateOrUpdateResourceBuilder":
        self._request.set_value(ZoneTable.c.name.name, value)
        return self

    def with_description(
        self, value: str
    ) -> "ZoneCreateOrUpdateResourceBuilder":
        self._request.set_value(ZoneTable.c.description.name, value)
        return self


class ZonesFilterQueryBuilder(FilterQueryBuilder):
    def with_ids(self, ids: list[int] | None) -> FilterQueryBuilder:
        if ids is not None:
            self.query.add_clause(ZoneTable.c.id.in_(ids))
        return self


class ZonesRepository(BaseRepository[Zone]):
    async def create(self, resource: CreateOrUpdateResource) -> Zone:
        stmt = (
            insert(ZoneTable)
            .returning(
                ZoneTable.c.id,
                ZoneTable.c.name,
                ZoneTable.c.description,
                ZoneTable.c.created,
                ZoneTable.c.updated,
            )
            .values(**resource.get_values())
        )
        try:
            result = await self.connection.execute(stmt)
        except IntegrityError:
            self._raise_already_existing_exception()
        zone = result.one()
        return Zone(**zone._asdict())

    async def find_by_id(self, id: int) -> Zone | None:
        stmt = self._select_all_statement().filter(eq(ZoneTable.c.id, id))

        result = await self.connection.execute(stmt)
        zone = result.first()
        if not zone:
            return None
        return Zone(**zone._asdict())

    async def find_by_name(self, name: str) -> Zone | None:
        stmt = self._select_all_statement().filter(eq(ZoneTable.c.name, name))

        result = await self.connection.execute(stmt)
        zone = result.first()
        if not zone:
            return None
        return Zone(**zone._asdict())

    async def list(
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[Zone]:
        # TODO: use the query for the filters
        stmt = (
            self._select_all_statement()
            .order_by(desc(ZoneTable.c.id))
            .limit(size + 1)  # Retrieve one more element to get the next token
        )

        if query:
            stmt = stmt.where(*query.get_clauses())

        if token is not None:
            stmt = stmt.where(le(ZoneTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id
        return ListResult[Zone](
            items=[Zone(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def update(self, id: int, resource: CreateOrUpdateResource) -> Zone:
        raise NotImplementedError("Not implemented yet.")

    async def delete(self, id: int) -> None:
        stmt = delete(ZoneTable).where(eq(ZoneTable.c.id, id))
        await self.connection.execute(stmt)

    async def get_default_zone(self) -> Zone:
        stmt = self._select_all_statement().join(
            DefaultResourceTable,
            eq(DefaultResourceTable.c.zone_id, ZoneTable.c.id),
        )
        result = await self.connection.execute(stmt)
        # By design the default zone is always present.
        zone = result.first()
        return Zone(**zone._asdict())

    def _select_all_statement(self) -> Select[Any]:
        return select(
            ZoneTable.c.id,
            ZoneTable.c.created,
            ZoneTable.c.updated,
            ZoneTable.c.name,
            ZoneTable.c.description,
        ).select_from(ZoneTable)
