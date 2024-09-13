#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Optional

from sqlalchemy import desc, insert, select, Select, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.sql.operators import eq, le

from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
    CreateOrUpdateResourceBuilder,
)
from maasservicelayer.db.tables import ResourcePoolTable
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.resource_pools import ResourcePool

RESOURCE_POOLS_FIELDS = (
    ResourcePoolTable.c.id,
    ResourcePoolTable.c.name,
    ResourcePoolTable.c.description,
    ResourcePoolTable.c.created,
    ResourcePoolTable.c.updated,
)


class ResourcePoolCreateOrUpdateResourceBuilder(CreateOrUpdateResourceBuilder):
    def with_name(
        self, value: str
    ) -> "ResourcePoolCreateOrUpdateResourceBuilder":
        self._request.set_value(ResourcePoolTable.c.name.name, value)
        return self

    def with_description(
        self, value: str
    ) -> "ResourcePoolCreateOrUpdateResourceBuilder":
        self._request.set_value(ResourcePoolTable.c.description.name, value)
        return self


class ResourcePoolClauseFactory(ClauseFactory):
    @classmethod
    def with_ids(cls, ids: Optional[list[int]]) -> Clause:
        return Clause(condition=ResourcePoolTable.c.id.in_(ids))


class ResourcePoolRepository(BaseRepository[ResourcePool]):
    async def find_by_id(self, id: int) -> Optional[ResourcePool]:
        stmt = self._select_all_statement().where(
            eq(ResourcePoolTable.c.id, id)
        )
        if result := await self.connection.execute(stmt):
            if resource_pools := result.one_or_none():
                return ResourcePool(**resource_pools._asdict())
        return None

    async def create(self, resource: CreateOrUpdateResource) -> ResourcePool:
        stmt = (
            insert(ResourcePoolTable)
            .returning(*RESOURCE_POOLS_FIELDS)
            .values(**resource.get_values())
        )
        try:
            result = await self.connection.execute(stmt)
        except IntegrityError:
            self._raise_already_existing_exception()
        resource_pools = result.one()
        return ResourcePool(**resource_pools._asdict())

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[ResourcePool]:
        stmt = (
            self._select_all_statement()
            .order_by(desc(ResourcePoolTable.c.id))
            .limit(size + 1)
        )
        if query and query.where:
            stmt = stmt.where(query.where.condition)

        if token is not None:
            stmt = stmt.where(le(ResourcePoolTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:
            next_token = result.pop().id
        return ListResult[ResourcePool](
            items=[ResourcePool(**row._asdict()) for row in result],
            next_token=next_token,
        )

    async def delete(self, id: int) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> ResourcePool:
        stmt = (
            update(ResourcePoolTable)
            .where(eq(ResourcePoolTable.c.id, id))
            .returning(*RESOURCE_POOLS_FIELDS)
            .values(**resource.get_values())
        )
        try:
            new_resource_pool = (await self.connection.execute(stmt)).one()
        except IntegrityError:
            self._raise_already_existing_exception()
        except NoResultFound:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Resource pool with id '{id}' does not exist.",
                    )
                ]
            )
        return ResourcePool(**new_resource_pool._asdict())

    async def list_ids(self) -> set[int]:
        stmt = select(ResourcePoolTable.c.id).select_from(ResourcePoolTable)
        result = (await self.connection.execute(stmt)).all()
        return {row.id for row in result}

    def _select_all_statement(self) -> Select[Any]:
        return select(*RESOURCE_POOLS_FIELDS).select_from(ResourcePoolTable)
