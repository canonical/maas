#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC

from sqlalchemy.sql.operators import ColumnOperators


class FilterQuery:
    """
    Represents the filters for a query.
    """

    def __init__(self):
        self.clauses = []

    def add_clause(self, clause: ColumnOperators):
        self.clauses.append(clause)

    def get_clauses(self) -> list[ColumnOperators]:
        return self.clauses

    def __eq__(self, other):
        """Useful for tests"""
        if not isinstance(other, type(self)):
            return False

        self_clauses = self.get_clauses()
        other_clauses = other.get_clauses()

        if len(self_clauses) != len(other_clauses):
            return False

        for self_clause, other_clause in zip(self_clauses, other_clauses):
            if str(
                self_clause.compile(compile_kwargs={"literal_binds": True})
            ) != str(
                other_clause.compile(compile_kwargs={"literal_binds": True})
            ):
                return False
        return True


class FilterQueryBuilder(ABC):
    """
    In the repositories you might want to extend this builder so to keep a consistent approach across
    all the repositories.
    """

    def __init__(self):
        self.query = FilterQuery()

    def build(self) -> FilterQuery:
        return self.query
