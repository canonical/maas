from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


@dataclass
class ListResult(Generic[T]):
    """
    Encapsulates the result of calling a Repository method than returns a list. It includes the items and the number of items
    that matched the query.
    """

    items: Sequence[T]
    total: int


class MaasBaseModel(ABC, BaseModel):
    @abstractmethod
    def etag(self) -> str:
        pass
