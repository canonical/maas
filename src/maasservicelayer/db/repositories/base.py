#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
)
from maasservicelayer.exceptions.constants import (
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult

T = TypeVar("T")


class CreateOrUpdateResource(dict):

    def get_values(self) -> dict[str, Any]:
        return self

    def set_value(self, key: str, value: Any) -> None:
        self[key] = value


class CreateOrUpdateResourceBuilder(ABC):
    """
    Every repository should provide a builder for their entity objects.
    """

    def __init__(self):
        self._request = CreateOrUpdateResource()

    def with_created(self, value: datetime) -> "CreateOrUpdateResourceBuilder":
        self._request.set_value("created", value)
        return self

    def with_updated(self, value: datetime) -> "CreateOrUpdateResourceBuilder":
        self._request.set_value("updated", value)
        return self

    def build(self) -> CreateOrUpdateResource:
        return self._request


class BaseRepository(ABC, Generic[T]):
    def __init__(self, connection: AsyncConnection):
        self.connection = connection

    @abstractmethod
    async def create(self, resource: CreateOrUpdateResource) -> T:
        pass

    @abstractmethod
    async def find_by_id(self, id: int) -> T | None:
        pass

    @abstractmethod
    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[T]:
        pass

    @abstractmethod
    async def update(self, id: int, resource: CreateOrUpdateResource) -> T:
        pass

    @abstractmethod
    async def delete(self, id: int) -> None:
        """
        If no resource with such `id` is found, silently ignore it and return `None` in any case.
        """
        pass

    def _raise_already_existing_exception(self):
        raise AlreadyExistsException(
            details=[
                BaseExceptionDetail(
                    type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                    message="A resource with such identifiers already exist.",
                )
            ]
        )
