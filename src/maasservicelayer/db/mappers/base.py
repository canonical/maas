#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import (
    Column,
    ColumnElement,
    false,
    Join,
    or_,
    Select,
    select,
    Table,
    true,
)
from sqlalchemy.engine import RowMapping

from maasservicelayer.db.filters import (
    Clause,
    ClauseFactory,
    OrderByClause,
    SQLQuerySpec,
)
from maasservicelayer.filters.base import (
    And,
    CustomFilter,
    FieldFilter,
    Filter,
    Not,
    Operator,
    Or,
)
from maasservicelayer.filters.query import (
    CustomOrderBy,
    OrderBy,
    Ordering,
    QuerySpec,
)
from maasservicelayer.models.base import ResourceBuilder

ModelT = TypeVar("ModelT", bound=BaseModel)
type StorageRow = Mapping[str, Any] | RowMapping


class CreateOrUpdateResource(dict):
    def get_values(self) -> dict[str, Any]:
        return self

    def set_value(self, key: str, value: Any) -> None:
        self[key] = value


class UnsupportedFilterError(Exception):
    pass


@dataclass(frozen=True)
class ColumnMapping:
    """Domain query expression, required joins, and optional writable column."""

    column: ColumnElement
    joins: tuple[Join, ...] = ()
    storage_column: Column[Any] | None = None


class BaseDomainDataMapper(ABC, Generic[ModelT]):
    """
    How the domain model should map to the data model.
    """

    def __init__(
        self,
        model: type[ModelT],
        table: Table,
        *,
        query_model: type[BaseModel] | None = None,
    ):
        self.model = model
        self.query_model = model if query_model is None else query_model
        self.table = table
        self.table_columns = {
            column_name: column for column_name, column in table.c.items()
        }

    def to_domain(self, row: StorageRow) -> ModelT:
        """Hydrate a domain model without mutating its storage row."""
        values = None
        for field in self.field_mappings():
            if field in row:
                continue
            column = self._writable_column(field)
            if column is None or column.name not in row:
                continue
            if values is None:
                values = dict(row)
            values[field] = row[column.name]
            if column.name not in self.model.model_fields:
                values.pop(column.name, None)
        return self.model(**(row if values is None else values))

    def select_statement(self) -> Select[Any]:
        """Select the storage representation consumed by this mapper."""
        return select(self.table).select_from(self.table)

    def _writable_column(self, field: str) -> Column[Any] | None:
        mapping = self.field_mappings().get(field)
        if mapping is None:
            return self.table_columns.get(field)
        column = mapping.storage_column
        if column is None and isinstance(mapping.column, Column):
            column = mapping.column
        if column is not None and column.table is self.table:
            return column
        return None

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

    def to_query(self, query: QuerySpec) -> SQLQuerySpec:
        """Translate domain filters and ordering into SQL clauses."""
        return SQLQuerySpec(
            where=self.to_clause(query.where)
            if query.where is not None
            else None,
            order_by=[
                self._order_by_clause(order) for order in query.order_by
            ],
        )

    def custom_order_by_clause(self, order: CustomOrderBy) -> OrderByClause:
        raise UnsupportedFilterError(
            f"{type(self).__name__} can't translate {type(order).__name__}."
        )

    def _order_by_clause(self, order: Ordering) -> OrderByClause:
        self._ensure_same_model(order.model)
        if isinstance(order, OrderBy):
            mapping = self._column_mapping(order.field)
            clause = OrderByClause(
                column=mapping.column, joins=list(mapping.joins)
            )
        else:
            clause = self.custom_order_by_clause(order)
        column = (
            clause.column.desc() if order.descending else clause.column.asc()
        )
        return OrderByClause(column=column, joins=clause.joins)

    def to_clause(self, filter: Filter) -> Clause:
        match filter:
            case And(filters):
                if not filters:
                    return Clause(condition=true())
                return ClauseFactory.and_clauses(
                    [self.to_clause(f) for f in filters]
                )
            case Or(filters):
                if not filters:
                    return Clause(condition=false())
                return ClauseFactory.or_clauses(
                    [self.to_clause(f) for f in filters]
                )
            case Not(inner):
                clause = self.to_clause(inner)
                # SQL UNKNOWN is a non-match, so its complement must match.
                return Clause(
                    condition=clause.condition.is_not(True), joins=clause.joins
                )
            case FieldFilter():
                self._ensure_same_model(filter.model)
                return self._field_clause(filter)
            case CustomFilter():
                self._ensure_same_model(filter.model)
                return self.custom_filter_clause(filter)
            case _:
                raise UnsupportedFilterError(
                    f"{type(self).__name__} can't translate "
                    f"{type(filter).__name__}."
                )

    def _ensure_same_model(self, model: type[BaseModel]) -> None:
        # A filter for another model may share field names with this one and
        # silently select the wrong rows.
        if not issubclass(self.query_model, model):
            raise UnsupportedFilterError(
                f"A query on {model.__name__} can't be applied to "
                f"{self.query_model.__name__}."
            )

    def _column_mapping(self, field: str) -> ColumnMapping:
        if (mapping := self.field_mappings().get(field)) is not None:
            return mapping
        if (column := self.table_columns.get(field)) is not None:
            return ColumnMapping(column)
        raise UnsupportedFilterError(
            f"{self.query_model.__name__}.{field} is not mapped to a column."
        )

    def _field_clause(self, filter: FieldFilter) -> Clause:
        mapping = self._column_mapping(filter.field)
        match filter.operator:
            case Operator.EQ:
                condition = mapping.column == filter.value
            case Operator.IN:
                values = tuple(filter.value)
                condition = mapping.column.in_(
                    [value for value in values if value is not None]
                )
                if any(value is None for value in values):
                    condition = or_(condition, mapping.column.is_(None))
            case _:
                raise UnsupportedFilterError(
                    f"Unsupported filter operator {filter.operator!r}."
                )
        return Clause(condition=condition, joins=list(mapping.joins))
