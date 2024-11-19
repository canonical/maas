#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from datetime import datetime
from operator import eq, le
from typing import Any, Generic, Type, TypeVar

from sqlalchemy import delete, desc, insert, select, Select, Table, update
from sqlalchemy.exc import IntegrityError, NoResultFound

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult, MaasBaseModel

T = TypeVar("T", bound=MaasBaseModel)


class CreateOrUpdateResource(dict):

    def get_values(self) -> dict[str, Any]:
        return self

    def set_value(self, key: str, value: Any) -> None:
        self[key] = value


class ResourceBuilder(ABC):
    """
    Every repository should provide a builder for their entity objects.
    """

    def __init__(self):
        self._request = CreateOrUpdateResource()

    def with_created(self, value: datetime) -> "ResourceBuilder":
        self._request.set_value("created", value)
        return self

    def with_updated(self, value: datetime) -> "ResourceBuilder":
        self._request.set_value("updated", value)
        return self

    def build(self) -> CreateOrUpdateResource:
        return self._request


class BaseRepository(ABC, Generic[T]):
    def __init__(self, context: Context):
        self.context = context
        self.connection = context.get_connection()

    @abstractmethod
    def get_repository_table(self) -> Table:
        pass

    @abstractmethod
    def get_model_factory(self) -> Type[T]:
        pass

    def select_all_statement(self) -> Select[Any]:
        return select(self.get_repository_table()).select_from(
            self.get_repository_table()
        )

    async def get(self, query: QuerySpec) -> list[T]:
        stmt = self.select_all_statement().where(query.where.condition)

        result = (await self.connection.execute(stmt)).all()
        return [self.get_model_factory()(**row._asdict()) for row in result]

    async def get_one(self, query: QuerySpec) -> T | None:
        stmt = (
            self.select_all_statement().where(query.where.condition).limit(1)
        )

        result = (await self.connection.execute(stmt)).one_or_none()
        if result:
            return self.get_model_factory()(**result._asdict())
        return None

    async def create(self, resource: CreateOrUpdateResource) -> T:
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

    async def find_by_id(self, id: int) -> T | None:
        stmt = self.select_all_statement().where(
            eq(self.get_repository_table().c.id, id),
        )
        result = (await self.connection.execute(stmt)).one_or_none()
        if result:
            return self.get_model_factory()(**result._asdict())
        return None

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[T]:
        stmt = (
            self.select_all_statement()
            .order_by(desc(self.get_repository_table().c.id))
            .limit(size + 1)
        )
        if query and query.where:
            stmt = stmt.where(query.where.condition)

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

    async def update(self, id: int, resource: CreateOrUpdateResource) -> T:
        stmt = (
            update(self.get_repository_table())
            .where(eq(self.get_repository_table().c.id, id))
            .returning(self.get_repository_table())
            .values(**resource.get_values())
        )
        try:
            updated_resource = (await self.connection.execute(stmt)).one()
        except IntegrityError:
            self._raise_already_existing_exception()
        except NoResultFound:
            self._raise_not_found_exception()
        return self.get_model_factory()(**updated_resource._asdict())

    async def delete(self, id: int) -> None:
        """
        If no resource with such `id` is found, silently ignore it and return `None` in any case.
        """
        stmt = delete(self.get_repository_table()).where(
            self.get_repository_table().c.id == id
        )
        await self.connection.execute(stmt)

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
