#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Filters expressed on domain model fields.

Filters describe which resources to select without referring to database
tables. The domain/data mapper of each repository translates them into SQL,
so services and API handlers don't depend on the data model.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel


class Operator(Enum):
    EQ = "eq"
    IN = "in"


@dataclass(frozen=True)
class FieldFilter:
    """Compares a single field of a domain model with a value."""

    model: type[BaseModel]
    field: str
    operator: Operator
    value: Any

    def __post_init__(self) -> None:
        if self.field not in self.model.model_fields:
            raise ValueError(
                f"{self.model.__name__} has no field '{self.field}'."
            )


@dataclass(frozen=True)
class CustomFilter:
    """Base class for filters that are not a comparison on a single field.

    Subclasses are frozen dataclasses that set `model` and are translated by
    the mapper of that model.
    """

    model: ClassVar[type[BaseModel]]


@dataclass(frozen=True)
class And:
    filters: tuple["Filter", ...]


@dataclass(frozen=True)
class Or:
    filters: tuple["Filter", ...]


@dataclass(frozen=True)
class Not:
    filter: "Filter"


type Filter = FieldFilter | CustomFilter | And | Or | Not


class FilterFactory:
    """Base class for the filters of a domain model."""

    model: ClassVar[type[BaseModel]]

    @classmethod
    def _equals(cls, field: str, value: Any) -> FieldFilter:
        return FieldFilter(cls.model, field, Operator.EQ, value)

    @classmethod
    def _is_in(cls, field: str, values: Iterable[Any]) -> FieldFilter:
        return FieldFilter(cls.model, field, Operator.IN, tuple(values))

    @staticmethod
    def and_filters(filters: Iterable[Filter]) -> And:
        return And(tuple(filters))

    @staticmethod
    def or_filters(filters: Iterable[Filter]) -> Or:
        return Or(tuple(filters))

    @staticmethod
    def not_filter(filter: Filter) -> Not:
        return Not(filter)
