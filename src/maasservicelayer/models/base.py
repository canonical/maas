# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import Any, Generic, Optional, Sequence, TypeVar, Union

from pydantic import BaseModel, create_model, Field
from pydantic.fields import ModelField

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


class Unset:
    """Sentinel object"""

    def __eq__(self, other):
        return other.__class__ is self.__class__


UNSET = Unset()

BaseModelT = TypeVar("BaseModelT", bound=MaasBaseModel)


def transform_field(field: ModelField) -> tuple[Any, Any]:
    # Each field can be Unset.
    new_field = Union[field.annotation, Unset]  # type: ignore
    return (new_field, UNSET)


# TODO: actually this function is NOT returning a type[BaseModelT]. We have to make it return type[ResourceBuilder] and find a
#  solution to provide type hints for the builders.
def make_builder(model: type[BaseModelT]) -> type[BaseModelT]:
    """
    Given a model, extract all the fields and the annotations to build a new ModelBuilder.
    The base of the new Builder is ResourceBuilder, because we want to have some specific functions for builders.

    We want to have a dedicated builder because when we create or update a resource we don't want to specify all the fields.
    For example, we want to define some default values at DB level.

    Heads up: this works in pydantic 1.x. When we move to 2.x we might have to change this.
    """
    return create_model(  # type: ignore
        f"{model.__name__}Builder",
        __base__=ResourceBuilder,
        __module__=ResourceBuilder.__module__,
        **{
            field_name: transform_field(field_info)
            for field_name, field_info in model.__fields__.items()
        },
    )
