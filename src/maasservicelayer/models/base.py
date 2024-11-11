# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import Any, Generic, Optional, Sequence, TypeVar

from pydantic import BaseModel, Field

from maasservicelayer.utils.date import utcnow

T = TypeVar("T")


@dataclass
class ListResult(Generic[T]):
    """
    Encapsulates the result of calling a Repository method than returns a list. It includes the items and the number of items
    that matched the query.
    """

    items: Sequence[T]
    # None if there is no next page
    next_token: Optional[str] = None


class MaasBaseModel(ABC, BaseModel):
    id: int

    def __eq__(self, other: Any) -> bool:
        # Pydantic is not comparing nested objects. This is the workaround to do it.
        if other.__class__ is self.__class__:
            return self.dict() == other.dict()
        return False

    @abstractmethod
    def etag(self) -> str:
        pass


class MaasTimestampedBaseModel(MaasBaseModel):
    created: datetime = Field(default=utcnow())
    updated: datetime = Field(default=utcnow())

    def etag(self) -> str:
        m = hashlib.sha256()
        m.update(self.updated.isoformat().encode("utf-8"))
        return m.hexdigest()
