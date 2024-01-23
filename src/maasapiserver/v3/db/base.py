from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.api.models.requests.query import PaginationParams
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
    async def find_by_id(self, id: str) -> Optional[T]:
        pass

    @abstractmethod
    async def list(self, pagination_params: PaginationParams) -> ListResult[T]:
        pass

    @abstractmethod
    async def update(self, id: str, request: K) -> T:
        pass

    @abstractmethod
    async def delete(self) -> None:
        pass
