#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from operator import eq, le
from typing import Any, Generic, List, Sequence, TypeVar

from sqlalchemy import delete, desc, insert, Row, select, Select, Table, update
from sqlalchemy.exc import IntegrityError

from maasservicelayer.context import Context
from maasservicelayer.db.filters import Clause, QuerySpec
from maasservicelayer.db.mappers.base import BaseDomainDataMapper
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import (
    ListResult,
    MaasBaseModel,
    MaasTimestampedBaseModel,
    ResourceBuilder,
)
from maasservicelayer.utils.date import utcnow


class MultipleResultsException(Exception):
    pass


T = TypeVar("T", bound=MaasBaseModel)


class BaseRepository(ABC, Generic[T]):
    def __init__(self, context: Context):
        self.context = context
        self.connection = context.get_connection()
        self.mapper = self.get_mapper()
        self.has_timestamped_fields = issubclass(
            self.get_model_factory(), MaasTimestampedBaseModel
        )

    @abstractmethod
    def get_repository_table(self) -> Table:
        pass

    @abstractmethod
    def get_model_factory(self) -> type[T]:
        pass

    def get_mapper(self) -> BaseDomainDataMapper:
        """
        How this repository should convert the domain model into the data model.
        """
        return DefaultDomainDataMapper(self.get_repository_table())

    def select_all_statement(self) -> Select[Any]:
        return select(self.get_repository_table()).select_from(
            self.get_repository_table()
        )

    async def get_many(self, query: QuerySpec) -> List[T]:
        return await self._get(query)

    async def get_by_id(self, id: int) -> T | None:
        return await self.get_one(
            QuerySpec(where=Clause(eq(self.get_repository_table().c.id, id)))
        )

    async def get_one(self, query: QuerySpec) -> T | None:
        results = await self._get(query)

        if results:
            if len(results) > 1:
                raise MultipleResultsException(
                    "Multiple results were returned by get_one."
                )
            return results[0]
        return None

    async def _get(self, query: QuerySpec) -> List[T]:
        stmt = self.select_all_statement()
        stmt = query.enrich_stmt(stmt)

        result = (await self.connection.execute(stmt)).all()
        return [self.get_model_factory()(**row._asdict()) for row in result]

    async def create(self, builder: ResourceBuilder) -> T:
        resource = self.mapper.build_resource(builder)
        if self.has_timestamped_fields:
            # Populate the fields only if the caller did not set them.
            now = utcnow()
            resource["created"] = resource.get("created", now)
            resource["updated"] = resource.get("updated", now)
        stmt = (
            insert(self.get_repository_table())
            .returning(self.get_repository_table())
            .values(**resource.get_values())
        )
        try:
            result = (await self.connection.execute(stmt)).one()
            return self.get_model_factory()(**result._asdict())
        except IntegrityError:
            self._raise_already_existing_exception()

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[T]:
        stmt = (
            self.select_all_statement()
            .order_by(desc(self.get_repository_table().c.id))
            .limit(size + 1)
        )
        if query:
            stmt = query.enrich_stmt(stmt)

        if token is not None:
            stmt = stmt.where(le(self.get_repository_table().c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()
        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id

        return ListResult[T](
            items=[
                self.get_model_factory()(**row._asdict()) for row in result
            ],
            next_token=next_token,
        )

    async def update_many(
        self, query: QuerySpec, builder: ResourceBuilder
    ) -> List[T]:
        updated_resources = await self._update(query, builder)
        return [
            self.get_model_factory()(**row._asdict())
            for row in updated_resources
        ]

    async def update_by_id(self, id: int, builder: ResourceBuilder) -> T:
        return await self.update_one(
            query=QuerySpec(
                where=Clause(eq(self.get_repository_table().c.id, id))
            ),
            builder=builder,
        )

    async def update_one(
        self, query: QuerySpec, builder: ResourceBuilder
    ) -> T:
        updated_resources = await self._update(query, builder)
        if not updated_resources:
            self._raise_not_found_exception()
        if len(updated_resources) > 1:
            raise MultipleResultsException()
        return self.get_model_factory()(**updated_resources[0]._asdict())

    async def _update(
        self, query: QuerySpec, builder: ResourceBuilder
    ) -> Sequence[Row]:
        resource = self.mapper.build_resource(builder)
        # Populate the updated field only if the caller did not set it.
        if self.has_timestamped_fields:
            now = utcnow()
            resource["updated"] = resource.get("updated", now)
        stmt = (
            update(self.get_repository_table())
            .returning(self.get_repository_table())
            .values(**resource.get_values())
        )
        stmt = query.enrich_stmt(stmt)
        try:
            updated_resources = (await self.connection.execute(stmt)).all()
        except IntegrityError:
            self._raise_already_existing_exception()
        return updated_resources

    async def delete_many(self, query: QuerySpec) -> List[T]:
        return await self._delete(query)

    async def delete_by_id(self, id: int) -> T | None:
        return await self.delete_one(
            query=QuerySpec(
                where=Clause(eq(self.get_repository_table().c.id, id))
            )
        )

    async def delete_one(self, query: QuerySpec) -> T | None:
        result = await self._delete(query)
        if not result:
            return None
        if len(result) > 1:
            raise MultipleResultsException(
                "Multiple results matched the delete_one query."
            )
        return result[0]

    async def _delete(self, query: QuerySpec) -> List[T]:
        """
        If no resource for the query is found, silently ignore it and return `None`.
        Otherwise, return the deleted resources.
        """
        stmt = delete(self.get_repository_table()).returning(
            self.get_repository_table()
        )
        stmt = query.enrich_stmt(stmt)
        results = (await self.connection.execute(stmt)).all()
        return [self.get_model_factory()(**row._asdict()) for row in results]

    def _raise_already_existing_exception(self):
        raise AlreadyExistsException(
            details=[
                BaseExceptionDetail(
                    type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                    message="A resource with such identifiers already exist.",
                )
            ]
        )

    def _raise_not_found_exception(self):
        raise NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                    message="Resource with such identifiers does not exist.",
                )
            ]
        )
