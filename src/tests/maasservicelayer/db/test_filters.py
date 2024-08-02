#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from sqlalchemy import ColumnOperators

from maasservicelayer.db.filters import FilterQuery


class TestFilterQuery:
    def test_get_clauses(self):
        query = FilterQuery()
        assert len(query.get_clauses()) == 0

        column_operator_mock = Mock(ColumnOperators)
        query.add_clause(column_operator_mock)
        assert len(query.get_clauses()) == 1
        assert query.get_clauses()[0] == column_operator_mock
