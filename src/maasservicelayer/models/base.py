# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import Any, Generic, Sequence, TypeVar

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
    total: int

    def has_next(self, page: int, size: int) -> bool:
        return self.total and page * size < self.total


class MaasBaseModel(BaseModel, ABC):
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


class ResourceBuilder(BaseModel):
    """
    The base class for all the builders.
    """

    class Config:
        """
        We need to set arbitrary_types_allowed = True so to have the sentinel object Unset.
        In any case, the make_builder function is going to generate the model from a class that extends BaseModel, so its field
        type can't have arbitrary types unless the original class has this config.
        """

        arbitrary_types_allowed = True

    def __eq__(self, other):
        # Pydantic is not comparing nested objects. This is the workaround to do it.
        if other.__class__ is self.__class__:
            return self.dict() == other.dict()
        return False

    def populated_fields(self) -> dict[str, Any]:
        """Returns the name, value of all the fields that aren't UNSET."""
        field_dict = self.dict(exclude_unset=True)
        # exclude all the UNSET values
        field_dict = {
            k: v for k, v in field_dict.items() if not isinstance(v, Unset)
        }
        return field_dict


class Unset:
    """Sentinel object"""

    def __eq__(self, other):
        return other.__class__ is self.__class__

    def __repr__(self):
        return "Unset"


UNSET = Unset()

BaseModelT = TypeVar("BaseModelT", bound=MaasBaseModel)


def generate_builder():
    def decorate(cls: type[T]) -> type[T]:
        setattr(cls, "__generate_builder__", True)
        return cls

    return decorate
