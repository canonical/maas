#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Query specifications expressed only in domain terms."""

from dataclasses import dataclass, replace
from typing import ClassVar

from pydantic import BaseModel

from maasservicelayer.filters.base import Filter


@dataclass(frozen=True)
class OrderBy:
    """Order resources by a domain field."""

    model: type[BaseModel]
    field: str
    descending: bool = False

    def __post_init__(self) -> None:
        if self.field not in self.model.model_fields:
            raise ValueError(
                f"{self.model.__name__} has no field '{self.field}'."
            )


@dataclass(frozen=True, kw_only=True)
class CustomOrderBy:
    """Ordering by a domain-specific rule rather than a single field."""

    model: ClassVar[type[BaseModel]]
    descending: bool = False


type Ordering = OrderBy | CustomOrderBy


class OrderByFactory:
    """Apply a direction to an immutable domain ordering."""

    @staticmethod
    def asc(order: Ordering) -> Ordering:
        return replace(order, descending=False)

    @staticmethod
    def desc(order: Ordering) -> Ordering:
        return replace(order, descending=True)


@dataclass(frozen=True)
class QuerySpec:
    """Select and order resources without referring to their storage."""

    where: Filter | None = None
    order_by: tuple[Ordering, ...] = ()
