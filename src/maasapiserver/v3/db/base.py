from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.db.filters import FilterQuery
from maasapiserver.v3.models.base import ListResult

T = TypeVar("T")

K = TypeVar("K")


class BaseRepository(ABC, Generic[T, K]):
    def __init__(self, connection: AsyncConnection):
        self.connection = connection

    @abstractmethod
    async def create(self, request: K) -> T:
        pass

    @abstractmethod
    async def find_by_id(self, id: int) -> T | None:
        pass

    @abstractmethod
    async def list(
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[T]:
        pass

    @abstractmethod
    async def update(self, resource: T) -> T:
        pass

    @abstractmethod
    async def delete(self, id: int) -> None:
        """
        If no resource with such `id` is found, silently ignore it and return `None` in any case.
        """
        pass
