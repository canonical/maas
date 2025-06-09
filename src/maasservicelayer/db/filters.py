# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass, field
from typing import TypeVar

from sqlalchemy import (
    and_,
    ColumnElement,
    Delete,
    Join,
    not_,
    or_,
    Select,
    Update,
)


@dataclass
class Clause:
    condition: ColumnElement
    joins: list[Join] = field(default_factory=list)

    def __eq__(self, other):
        """Useful for tests"""
        if not isinstance(other, type(self)):
            return False
        if len(self.joins) != len(other.joins):
            return False
        for self_join in self.joins:
            # check the i-th join with all the other and return False if none matches
            if all(
                [
                    not self_join.compare(other_join)
                    for other_join in other.joins
                ]
            ):
                return False
        return self.condition.compare(other.condition)


SUD = TypeVar("SUD", Select, Update, Delete)
UD = TypeVar("UD", Update, Delete)


@dataclass
class QuerySpec:
    """
    Contains the query specification to be executed.
    """

    where: Clause | None = None
    # In the future this is the right place where we will put additional query pieces
    # order_by: Clause | None = None

    def enrich_stmt(self, stmt: SUD) -> SUD:
        """Enrich the SQL statement by adding the clauses (if present) in the object.

        The purpose of this method is to handle all the logic for enriching a statement
        in a single spot, so when you have to apply a QuerySpec to a statement, all you
        have to do is: `stmt = query.enrich_stmt(stmt)`, where `query` is the QuerySpec
        object.

        The where condition is added to all kind of statements through the .where() method,
        the join conditions, instead, works different based on the statement type.
        For the Select statement we can add them through either the join or join_from() method.
        For the Update/Delete statements we can leverage the UPDATE .. FROM and
        DELETE .. USING syntax that PostgreSQL uses. To do this, we have to specify
        the join condition inside the where clause and SQLAlchemy will do the rest.
        In both cases, we only add the join if it's not redundant.

        Params:
            stmt: the SQL statement to enrich
        Returns:
            The original statement (possibly) enriched with the clauses.
        """
        if not self.where:
            return stmt

        stmt = stmt.where(self.where.condition)

        if isinstance(stmt, Select):
            stmt = self._enrich_select_stmt(stmt)
        elif isinstance(stmt, (Update, Delete)):
            stmt = self._enrich_update_delete_stmt(stmt)

        return stmt

    def _enrich_select_stmt(self, stmt: Select) -> Select:
        already_joined = self._get_already_joined(stmt)

        for join in self.where.joins:  # type: ignore
            left_in_joined = join.left in already_joined
            right_in_joined = join.right in already_joined

            if not left_in_joined and not right_in_joined:
                stmt = stmt.join_from(join.left, join.right, join.onclause)
                already_joined.update([join.left, join.right])
            elif not left_in_joined:
                stmt = stmt.join(join.left, join.onclause)
                already_joined.add(join.left)
            elif not right_in_joined:
                stmt = stmt.join(join.right, join.onclause)
                already_joined.add(join.right)

        return stmt

    def _enrich_update_delete_stmt(self, stmt: UD) -> UD:
        for join in self.where.joins:  # type: ignore
            assert join.onclause is not None, "Join onclause must be defined."
            if all(
                not join.onclause.compare(existing)
                for existing in stmt._where_criteria
            ):
                stmt = stmt.where(join.onclause)
        return stmt

    def _get_already_joined(self, stmt: Select) -> set:
        already_joined = {
            item for join in stmt._setup_joins for item in (join[0], join[2])
        }
        already_joined.update(stmt.columns_clause_froms)
        return already_joined


class ClauseFactory:
    @staticmethod
    def _combine_joins(clauses: list[Clause]) -> list[Join]:
        joins = []
        for clause in clauses:
            if clause.joins is not None:
                joins.extend(clause.joins)
        return joins

    @classmethod
    def or_clauses(cls, clauses: list[Clause]):
        return Clause(
            condition=or_(*[clause.condition for clause in clauses]),
            joins=cls._combine_joins(clauses),
        )

    @classmethod
    def and_clauses(cls, clauses: list[Clause]):
        return Clause(
            condition=and_(*[clause.condition for clause in clauses]),
            joins=cls._combine_joins(clauses),
        )

    @classmethod
    def not_clause(cls, clause: Clause):
        return Clause(condition=not_(clause.condition), joins=clause.joins)
