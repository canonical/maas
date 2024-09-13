#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from dataclasses import dataclass

from sqlalchemy import and_, ColumnElement, or_


@dataclass
class Clause:
    condition: ColumnElement
    # This class will contain more info in the future. For example the joins required for a specific query.

    def __eq__(self, other):
        """Useful for tests"""
        if not isinstance(other, type(self)):
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


class ClauseFactory:
    @classmethod
    def or_clauses(cls, clauses: list[Clause]):
        return Clause(
            condition=or_(*[clause.condition for clause in clauses]),
        )

    @classmethod
    def and_clauses(cls, clauses: list[Clause]):
        return Clause(
            condition=and_(*[clause.condition for clause in clauses]),
        )
