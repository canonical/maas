#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import literal, literal_column

from maasservicelayer.db.filters import Clause, ClauseFactory


class TestClauseFactory:
    def test_or(self):
        clause = ClauseFactory.or_clauses(
            [
                Clause(condition=literal(0)),
                Clause(condition=literal(1)),
                Clause(condition=literal(2)),
            ]
        )
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "0 OR 1 OR 2"
        )

    def test_and(self):
        clause = ClauseFactory.and_clauses(
            [
                Clause(condition=literal(0)),
                Clause(condition=literal(1)),
                Clause(condition=literal(2)),
            ]
        )
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "0 AND 1 AND 2"
        )

    def test_combined(self):
        clause = ClauseFactory.or_clauses(
            [
                ClauseFactory.and_clauses(
                    [
                        ClauseFactory.or_clauses(
                            [
                                Clause(condition=literal(0)),
                                Clause(condition=literal(5)),
                            ]
                        ),
                        Clause(condition=literal(3)),
                        ClauseFactory.or_clauses(
                            [
                                Clause(
                                    condition=literal_column(
                                        "test_column = 'value'"
                                    )
                                ),
                                Clause(condition=literal(8)),
                            ]
                        ),
                    ]
                ),
                ClauseFactory.and_clauses(
                    [
                        ClauseFactory.or_clauses(
                            [
                                Clause(condition=literal(2)),
                                Clause(
                                    condition=literal_column(
                                        "other_column LIKE '%search%'"
                                    )
                                ),
                            ]
                        ),
                        Clause(condition=literal(6)),
                    ]
                ),
                Clause(condition=literal(1)),
            ]
        )
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "(0 OR 5) AND 3 AND (test_column = 'value' OR 8) OR (2 OR other_column LIKE '%search%') AND 6 OR 1"
        )
