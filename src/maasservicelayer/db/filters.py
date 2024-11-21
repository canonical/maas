#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from dataclasses import dataclass, field
from typing import Union

from sqlalchemy import and_, ColumnElement, Delete, Join, or_, Select, Update


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


@dataclass
class QuerySpec:
    """
    Contains the query specification to be executed.
    """

    where: Clause | None = None
    # In the future this is the right place where we will put additional query pieces
    # order_by: Clause | None = None

    def enrich_stmt(
        self, stmt: Union[Select, Update, Delete]
    ) -> Union[Select, Update, Delete]:
        """Enrich the SQL statement by adding the clauses (if present) in the object.

        The purpose of this method is to handle all the logic for enriching a statement
        in a single spot, so when you have to apply a QuerySpec to a statement, all you
        have to do is: `stmt = query.enrich_stmt(stmt)`, where `query` is the QuerySpec
        object.

        The where condition is added to all kind of statements through the .where() method,
        the join conditions, instead, works different based on the statement type.
        For the Select statement we can add it through the join_from() method.
        For the Update/Delete statements we can leverage the UPDATE .. FROM and
        DELETE .. USING syntax that PostgreSQL uses. To do this, we have to specify
        the join condition inside the where clause and SQLAlchemy will do the rest.

        Params:
            stmt: the SQL statement to enrich
        Returns:
            The original statement (possibly) enriched with the clauses.
        """
        if isinstance(stmt, Select):
            if self.where:
                stmt = stmt.where(self.where.condition)
                for j in self.where.joins:
                    stmt = stmt.join_from(j.left, j.right, j.onclause)
        elif isinstance(stmt, Update) or isinstance(stmt, Delete):
            if self.where:
                stmt = stmt.where(self.where.condition)
                for j in self.where.joins:
                    # we want to make sure that the onclause is set
                    assert j.onclause is not None
                    stmt = stmt.where(j.onclause)
        return stmt


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
