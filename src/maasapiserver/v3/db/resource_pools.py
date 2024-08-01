from typing import Any, Optional

from sqlalchemy import desc, insert, select, Select, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.sql.operators import eq, le

from maasapiserver.common.db.filters import FilterQuery
from maasapiserver.common.db.tables import ResourcePoolTable
from maasapiserver.common.models.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasapiserver.common.models.exceptions import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasapiserver.v3.db.base import (
    BaseRepository,
    CreateOrUpdateResource,
    CreateOrUpdateResourceBuilder,
)
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.resource_pools import ResourcePool

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
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[ResourcePool]:
        # TODO: use the query for the filters
        stmt = (
            self._select_all_statement()
            .order_by(desc(ResourcePoolTable.c.id))
            .limit(size + 1)
        )

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

    def _select_all_statement(self) -> Select[Any]:
        return select(*RESOURCE_POOLS_FIELDS).select_from(ResourcePoolTable)
