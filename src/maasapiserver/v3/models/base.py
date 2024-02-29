from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import hashlib
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
    id: int

    @abstractmethod
    def etag(self) -> str:
        pass


class MaasTimestampedBaseModel(MaasBaseModel):
    created: datetime
    updated: datetime

    def etag(self) -> str:
        m = hashlib.sha256()
        m.update(self.updated.isoformat().encode("utf-8"))
        return m.hexdigest()
