#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
import ipaddress
from operator import eq
from typing import Any, Generic, List, Sequence, TypeVar

import psycopg2.extensions
import psycopg2.extras
from sqlalchemy import (
    Connection,
    CursorResult,
    delete,
    desc,
    insert,
    Row,
    Select,
    select,
    Table,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.functions import count

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


def cast_ip(s, cur):
    if s is None:
        return None
    return ipaddress.ip_address(str(s))


def cast_cidr(s, cur):
    if s is None:
        return None
    return ipaddress.ip_network(str(s))


class MultipleResultsException(Exception):
    pass


T = TypeVar("T", bound=MaasBaseModel)


class Repository(ABC):  # noqa: B024
    def __init__(self, context: Context):
        self.context = context

    # TODO: remove this when the connection in context is changed back to the AsyncConnection type only.
    async def execute_stmt(self, stmt) -> CursorResult[Any]:
        """
        Execute the given SQL statement, handling type conversions appropriately
        based on the database driver used.

        This method ensures consistent behavior between different database
        drivers (asyncpg and psycopg2) by registering and restoring necessary
        type casters on the connection executing the query.

        Type Conversion Considerations:
        1. JSONB Handling:
           - Django expects `jsonb` columns as strings to allow programmatic
             JSON parsing in `JsonField`.
           - In contrast, asyncpg returns `jsonb` columns as dictionaries.

        2. INET and CIDR Types:
           - `asyncpg` automatically converts PostgreSQL `INET` and `CIDR`
             types to `ipaddress.IPv4Address`, `ipaddress.IPv6Address`,
             `ipaddress.IPv4Network`, or `ipaddress.IPv6Network`.
             NOTE: this behaviour has been modified and now it converts
             `INET` to `netaddr.IPAddress` and `CIDR` to `netaddr.IPNetwork`.
             See src/maasservicelayer/db/__init__.py.
           - `psycopg2`, by default, returns these types as plain strings.

        Important:
        - Given that the service layer and its domain models are the future, we want to keep the default behavior of asyncpg
        and install/remove casters as needed for psycopg2.
        - If you have to use `register_adapter`, do so in maasserver/djangosettings/__init__.py as
          it applies globally to all connections.
        """
        connection = self.context.get_connection()
        if isinstance(connection, Connection):
            # This is a psycopg2 connection handled by django, attach the casters so that psycopg2 ends up with the same
            # behavior of asyncpg.
            try:
                psycopg2.extras.register_default_jsonb(
                    conn_or_curs=connection.connection.dbapi_connection  # type: ignore
                )
                cidr = psycopg2.extensions.new_type((650,), "CIDR", cast_cidr)
                inet = psycopg2.extensions.new_type((869,), "INET", cast_ip)
                psycopg2.extensions.register_type(
                    cidr,
                    connection.connection.dbapi_connection,  # type: ignore
                )
                psycopg2.extensions.register_type(
                    inet,
                    connection.connection.dbapi_connection,  # type: ignore
                )

                return connection.execute(stmt)
            finally:
                # Give this connection back to django and reset the default jsonb handler
                # https://github.com/django/django/blob/f609a2da868b2320ecdc0551df3cca360d5b5bc3/django/db/backends/postgresql/base.py#L339
                psycopg2.extras.register_default_jsonb(
                    conn_or_curs=connection.connection.dbapi_connection,  # type: ignore
                    loads=lambda x: x,
                )
                # Just return the string as is.
                cidr = psycopg2.extensions.new_type(
                    (650,), "CIDR", lambda x, y: x
                )
                inet = psycopg2.extensions.new_type(
                    (869,), "INET", lambda x, y: x
                )
                psycopg2.extensions.register_type(
                    cidr,
                    connection.connection.dbapi_connection,  # type: ignore
                )
                psycopg2.extensions.register_type(
                    inet,
                    connection.connection.dbapi_connection,  # type: ignore
                )

        else:
            return await connection.execute(stmt)


class ReadOnlyRepository(Repository, Generic[T]):
    def __init__(self, context: Context):
        super().__init__(context)
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

    async def exists(self, query: QuerySpec) -> bool:
        exists_stmt = select(self.get_repository_table().c.id).select_from(
            self.get_repository_table()
        )
        exists_stmt = query.enrich_stmt(exists_stmt).exists()
        stmt = select(exists_stmt)
        return (await self.execute_stmt(stmt)).scalar()

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

        result = (await self.execute_stmt(stmt)).all()
        return [self.get_model_factory()(**row._asdict()) for row in result]

    async def list(
        self, page: int, size: int, query: QuerySpec | None = None
    ) -> ListResult[T]:
        total_stmt = select(count()).select_from(self.get_repository_table())
        if query:
            total_stmt = query.enrich_stmt(total_stmt)
        total = (await self.execute_stmt(total_stmt)).scalar()

        stmt = (
            self.select_all_statement()
            .order_by(desc(self.get_repository_table().c.id))
            .offset((page - 1) * size)
            .limit(size)
        )
        if query:
            stmt = query.enrich_stmt(stmt)

        result = (await self.execute_stmt(stmt)).all()
        return ListResult[T](
            items=[
                self.get_model_factory()(**row._asdict()) for row in result
            ],
            total=total,
        )


class BaseRepository(ReadOnlyRepository[T], Generic[T]):
    def __init__(self, context: Context):
        super().__init__(context)

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
            result = (await self.execute_stmt(stmt)).one()
            return self.get_model_factory()(**result._asdict())
        except IntegrityError:
            self._raise_already_existing_exception()

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
            updated_resources = (await self.execute_stmt(stmt)).all()
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
        results = (await self.execute_stmt(stmt)).all()
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
