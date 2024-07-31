#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import abc

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


class FilterQueryBuilder(abc.ABC):
    """
    In the repositories you might want to extend this builder so to keep a consistent approach across
    all the repositories.
    """

    def __init__(self):
        self.query = FilterQuery()

    def build(self) -> FilterQuery:
        return self.query
