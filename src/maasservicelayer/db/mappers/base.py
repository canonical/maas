#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Join, Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.filters.base import (
    And,
    CustomFilter,
    FieldFilter,
    Filter,
    Not,
    Operator,
    Or,
)
from maasservicelayer.models.base import ResourceBuilder


class CreateOrUpdateResource(dict):
    def get_values(self) -> dict[str, Any]:
        return self

    def set_value(self, key: str, value: Any) -> None:
        self[key] = value


class UnsupportedFilterError(Exception):
    pass


@dataclass(frozen=True)
class ColumnMapping:
    """The SQL expression that stores a domain field, and the joins it needs."""

    column: ColumnElement
    joins: tuple[Join, ...] = ()


class BaseDomainDataMapper(ABC):
    """
    How the domain model should map to the data model.
    """

    def __init__(self, model: type[BaseModel], table: Table):
        self.model = model
        self.table_columns = {
            column_name: column for column_name, column in table.c.items()
        }

    @abstractmethod
    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        pass

    def field_mappings(self) -> dict[str, ColumnMapping]:
        """Domain fields that are not stored in a column with the same name."""
        return {}

    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        raise UnsupportedFilterError(
            f"{type(self).__name__} can't translate {type(filter).__name__}."
        )

    def to_clause(self, filter: Filter) -> Clause:
        match filter:
            case And(filters):
                return ClauseFactory.and_clauses(
                    [self.to_clause(f) for f in filters]
                )
            case Or(filters):
                return ClauseFactory.or_clauses(
                    [self.to_clause(f) for f in filters]
                )
            case Not(inner):
                return ClauseFactory.not_clause(self.to_clause(inner))
            case FieldFilter():
                self._ensure_same_model(filter.model)
                return self._field_clause(filter)
            case CustomFilter():
                self._ensure_same_model(filter.model)
                return self.custom_filter_clause(filter)

    def _ensure_same_model(self, model: type[BaseModel]) -> None:
        # A filter for another model may share field names with this one and
        # silently select the wrong rows.
        if model is not self.model:
            raise UnsupportedFilterError(
                f"A filter on {model.__name__} can't be applied to "
                f"{self.model.__name__}."
            )

    def _column_mapping(self, field: str) -> ColumnMapping:
        if (mapping := self.field_mappings().get(field)) is not None:
            return mapping
        if (column := self.table_columns.get(field)) is not None:
            return ColumnMapping(column)
        raise UnsupportedFilterError(
            f"{self.model.__name__}.{field} is not mapped to a column."
        )

    def _field_clause(self, filter: FieldFilter) -> Clause:
        mapping = self._column_mapping(filter.field)
        match filter.operator:
            case Operator.EQ:
                condition = mapping.column == filter.value
            case Operator.IN:
                condition = mapping.column.in_(filter.value)
        return Clause(condition=condition, joins=list(mapping.joins))
