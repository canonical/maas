# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

import pytest
from sqlalchemy import (
    asc,
    BigInteger,
    Column,
    create_engine,
    delete,
    ForeignKey,
    join,
    literal,
    literal_column,
    select,
    Table,
    update,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import MetaData

from maasservicelayer.db.filters import (
    Clause,
    ClauseFactory,
    OrderByClause,
    SQLQuerySpec,
)
from maasservicelayer.filters.sshkeys import SshKeyFilters

METADATA = MetaData()

A = Table(
    "test_table_a",
    METADATA,
    Column("id", BigInteger),
    Column("b_id", BigInteger, ForeignKey("test_table_b.id")),
)

B = Table(
    "test_table_b",
    METADATA,
    Column("id", BigInteger),
    Column("c_id", BigInteger, ForeignKey("test_table_c.id")),
)

C = Table(
    "test_table_c",
    METADATA,
    Column("id", BigInteger),
)


class TestClause:
    def test_compare_condition(self):
        c1 = Clause(condition=literal(0))
        c2 = Clause(condition=literal(0))
        assert c1 == c2

    def test_compare_joins_ordered(self):
        join1 = join(A, B, eq(A.c.b_id, B.c.id))
        join2 = join(B, C, eq(B.c.c_id, C.c.id))
        c1 = Clause(condition=literal(0), joins=[join1, join2])
        c2 = Clause(condition=literal(0), joins=[join1, join2])
        assert c1 == c2

    def test_compare_joins_unordered(self):
        join1 = join(A, B, eq(A.c.b_id, B.c.id))
        join2 = join(B, C, eq(B.c.c_id, C.c.id))
        c1 = Clause(condition=literal(0), joins=[join1, join2])
        c2 = Clause(condition=literal(0), joins=[join2, join1])
        assert c1 == c2

    def test_compare_different_joins(self):
        join1 = join(A, B, eq(A.c.b_id, B.c.id))
        join2 = join(B, C, eq(B.c.c_id, C.c.id))
        c1 = Clause(condition=literal(0), joins=[join1])
        c2 = Clause(condition=literal(0), joins=[join2])
        assert c1 != c2

    def test_compare_different_joins_different_length(self):
        join1 = join(A, B, eq(A.c.b_id, B.c.id))
        join2 = join(B, C, eq(B.c.c_id, C.c.id))
        c1 = Clause(condition=literal(0), joins=[join1])
        c2 = Clause(condition=literal(0), joins=[join1, join2])
        assert c1 != c2
        assert c2 != c1


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

    def test_join_one(self):
        join1 = join(A, B, eq(A.c.b_id, B.c.id))
        joins = ClauseFactory._combine_joins(
            [
                Clause(
                    condition=literal(1),
                    joins=[join1],
                ),
                Clause(condition=literal(1)),
            ]
        )

        assert joins == [join1]

    def test_join_two(self):
        join1 = join(A, B, eq(A.c.b_id, B.c.id))
        join2 = join(B, C, eq(B.c.c_id, C.c.id))
        joins = ClauseFactory._combine_joins(
            [
                Clause(
                    condition=literal(1),
                    joins=[join1],
                ),
                Clause(
                    condition=literal(2),
                    joins=[join2],
                ),
            ]
        )

        assert joins == [join1, join2]


class TestQuerySpec:
    @pytest.mark.parametrize(
        "statement, expected",
        [
            (select(B.c.id).select_from(A).join(B, A.c.b_id == B.c.id), [2]),
            (select(B.c.id).select_from(A.join(B, A.c.b_id == B.c.id)), [2]),
            (select(A.c.id), [1]),
        ],
    )
    def test_existing_roots_are_not_confused_with_where_references(
        self, statement, expected
    ):
        query = SQLQuerySpec(
            where=Clause(
                condition=B.c.id == 2,
                joins=[A.join(B, A.c.b_id == B.c.id)],
            )
        )
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                METADATA.create_all(connection)
                connection.execute(B.insert(), [{"id": 2}])
                connection.execute(A.insert(), [{"id": 1, "b_id": 2}])
                assert (
                    list(
                        connection.execute(
                            query.enrich_stmt(statement)
                        ).scalars()
                    )
                    == expected
                )
        finally:
            engine.dispose()

    def test_enrich_stmt_select_where(self):
        stmt = select(A.c.id)
        query = SQLQuerySpec(
            where=Clause(
                condition=eq(B.c.id, 1),
                joins=[join(A, B, eq(A.c.b_id, B.c.id))],
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "SELECT test_table_a.id FROM test_table_a JOIN test_table_b ON test_table_a.b_id = test_table_b.id WHERE test_table_b.id = 1"
        )

    def test_enrich_stmt_select_order_by(self):
        stmt = select(A.c.id)
        query = SQLQuerySpec(
            order_by=[
                OrderByClause(
                    column=asc(A.c.id),
                )
            ]
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "SELECT test_table_a.id FROM test_table_a ORDER BY test_table_a.id ASC"
        )

    def test_enrich_stmt_select_combined(self):
        stmt = select(A.c.id)
        query = SQLQuerySpec(
            where=Clause(
                condition=eq(B.c.id, 1),
                joins=[join(A, B, eq(A.c.b_id, B.c.id))],
            ),
            order_by=[
                OrderByClause(
                    column=asc(A.c.id),
                )
            ],
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "SELECT test_table_a.id FROM test_table_a JOIN test_table_b ON test_table_a.b_id = test_table_b.id WHERE test_table_b.id = 1 ORDER BY test_table_a.id ASC"
        )

    def test_enrich_stmt_update(self):
        stmt = update(A).values(id=100)
        query = SQLQuerySpec(
            where=Clause(
                condition=eq(B.c.id, 1),
                joins=[join(A, B, eq(A.c.b_id, B.c.id))],
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "UPDATE test_table_a SET id=100 FROM test_table_b WHERE test_table_b.id = 1 AND test_table_a.b_id = test_table_b.id"
        )

    def test_enrich_stmt_update_order_by(self):
        stmt = update(A).values(id=100)
        query = SQLQuerySpec(
            order_by=[
                OrderByClause(
                    column=asc(A.c.id),
                )
            ]
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "UPDATE test_table_a SET id=100"
        )

    def test_enrich_stmt_delete(self):
        stmt = delete(A).where(A.c.id < 3)
        query = SQLQuerySpec(
            where=Clause(
                condition=eq(B.c.id, 1),
                joins=[join(A, B, eq(A.c.b_id, B.c.id))],
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "DELETE FROM test_table_a USING test_table_b WHERE test_table_a.id < 3 AND test_table_b.id = 1 AND test_table_a.b_id = test_table_b.id"
        )

    def test_enrich_stmt_delete_order_by(self):
        stmt = delete(A).where(A.c.id < 3)
        query = SQLQuerySpec(
            order_by=[
                OrderByClause(
                    column=asc(A.c.id),
                )
            ]
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "DELETE FROM test_table_a WHERE test_table_a.id < 3"
        )

    def test_enrich_stmt_select_multiple_joins(self):
        stmt = select(A.c.id)
        query = SQLQuerySpec(
            ClauseFactory.and_clauses(
                [
                    Clause(
                        condition=eq(B.c.id, 1),
                        joins=[join(A, B, eq(A.c.b_id, B.c.id))],
                    ),
                    Clause(
                        condition=eq(C.c.id, 2),
                        joins=[join(B, C, eq(C.c.id, B.c.c_id))],
                    ),
                ]
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "SELECT test_table_a.id FROM test_table_a JOIN test_table_b ON test_table_a.b_id = test_table_b.id JOIN test_table_c ON test_table_c.id = test_table_b.c_id WHERE test_table_b.id = 1 AND test_table_c.id = 2"
        )

    def test_enrich_stmt_update_multiple_joins(self):
        stmt = update(A).values(id=100)
        query = SQLQuerySpec(
            ClauseFactory.and_clauses(
                [
                    Clause(
                        condition=eq(B.c.id, 1),
                        joins=[join(A, B, eq(A.c.b_id, B.c.id))],
                    ),
                    Clause(
                        condition=eq(C.c.id, 2),
                        joins=[join(B, C, eq(C.c.id, B.c.c_id))],
                    ),
                ]
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "UPDATE test_table_a SET id=100 FROM test_table_b, test_table_c WHERE test_table_b.id = 1 AND test_table_c.id = 2 AND test_table_a.b_id = test_table_b.id AND test_table_c.id = test_table_b.c_id"
        )

    def test_enrich_stmt_delete_multiple_joins(self):
        stmt = delete(A).where(A.c.id < 3)
        query = SQLQuerySpec(
            ClauseFactory.and_clauses(
                [
                    Clause(
                        condition=eq(B.c.id, 1),
                        joins=[join(A, B, eq(A.c.b_id, B.c.id))],
                    ),
                    Clause(
                        condition=eq(C.c.id, 2),
                        joins=[join(B, C, eq(C.c.id, B.c.c_id))],
                    ),
                ]
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "DELETE FROM test_table_a USING test_table_b, test_table_c WHERE test_table_a.id < 3 AND test_table_b.id = 1 AND test_table_c.id = 2 AND test_table_a.b_id = test_table_b.id AND test_table_c.id = test_table_b.c_id"
        )

    def test_enrich_stmt_select_multiple_redundant_joins(self):
        stmt = select(A.c.id)
        query = SQLQuerySpec(
            ClauseFactory.and_clauses(
                [
                    Clause(
                        condition=eq(B.c.id, 1),
                        joins=[
                            join(A, B, eq(A.c.b_id, B.c.id)),
                            join(B, C, eq(B.c.c_id, C.c.id)),
                        ],
                    ),
                    Clause(
                        condition=eq(B.c.id, 2),
                        joins=[join(B, C, eq(B.c.c_id, C.c.id))],
                    ),
                ]
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "SELECT test_table_a.id FROM test_table_a JOIN test_table_b ON test_table_a.b_id = test_table_b.id JOIN test_table_c ON test_table_b.c_id = test_table_c.id WHERE test_table_b.id = 1 AND test_table_b.id = 2"
        )

    def test_enrich_stmt_select_with_initial_joins(self):
        stmt = select(A.c.id).join_from(A, B, eq(A.c.b_id, B.c.id))
        query = SQLQuerySpec(
            ClauseFactory.and_clauses(
                [
                    Clause(
                        condition=eq(B.c.id, 1),
                        joins=[
                            join(A, B, eq(A.c.b_id, B.c.id)),
                            join(B, C, eq(B.c.c_id, C.c.id)),
                        ],
                    ),
                    Clause(
                        condition=eq(B.c.id, 2),
                        joins=[join(B, C, eq(B.c.c_id, C.c.id))],
                    ),
                ]
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "SELECT test_table_a.id FROM test_table_a JOIN test_table_b ON test_table_a.b_id = test_table_b.id JOIN test_table_c ON test_table_b.c_id = test_table_c.id WHERE test_table_b.id = 1 AND test_table_b.id = 2"
        )

    def test_enrich_stmt_update_redundant_joins(self):
        stmt = update(A).values(id=100)
        query = SQLQuerySpec(
            ClauseFactory.and_clauses(
                [
                    Clause(
                        condition=eq(B.c.id, 1),
                        joins=[join(A, B, eq(A.c.b_id, B.c.id))],
                    ),
                    Clause(
                        condition=eq(B.c.id, 2),
                        joins=[join(A, B, eq(A.c.b_id, B.c.id))],
                    ),
                ]
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "UPDATE test_table_a SET id=100 FROM test_table_b WHERE test_table_b.id = 1 AND test_table_b.id = 2 AND test_table_a.b_id = test_table_b.id"
        )

    def test_enrich_stmt_delete_redundant_joins(self):
        stmt = delete(A).where(A.c.id < 3)
        query = SQLQuerySpec(
            ClauseFactory.and_clauses(
                [
                    Clause(
                        condition=eq(B.c.id, 1),
                        joins=[join(A, B, eq(A.c.b_id, B.c.id))],
                    ),
                    Clause(
                        condition=eq(B.c.id, 2),
                        joins=[join(A, B, eq(A.c.b_id, B.c.id))],
                    ),
                ]
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "DELETE FROM test_table_a USING test_table_b WHERE test_table_a.id < 3 AND test_table_b.id = 1 AND test_table_b.id = 2 AND test_table_a.b_id = test_table_b.id"
        )

    def test_enrich_stmt_select_keeps_outer_join(self):
        stmt = select(A.c.id)
        query = SQLQuerySpec(
            Clause(
                condition=eq(B.c.id, 1),
                joins=[join(A, B, eq(A.c.b_id, B.c.id), isouter=True)],
            )
        )
        stmt = query.enrich_stmt(stmt)
        assert (
            str(
                stmt.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).replace("\n", "")
            == "SELECT test_table_a.id FROM test_table_a LEFT OUTER JOIN test_table_b ON test_table_a.b_id = test_table_b.id WHERE test_table_b.id = 1"
        )

    def test_enrich_stmt_select_rejects_outer_join_from_right_side(self):
        stmt = select(B.c.id)
        query = SQLQuerySpec(
            Clause(
                condition=eq(A.c.id, 1),
                joins=[join(A, B, eq(A.c.b_id, B.c.id), isouter=True)],
            )
        )
        with pytest.raises(ValueError):
            query.enrich_stmt(stmt)

    @pytest.mark.parametrize(
        "statement", [select(A.c.id), update(A), delete(A)]
    )
    def test_enrich_stmt_rejects_untranslated_filter(self, statement):
        with pytest.raises(TypeError):
            query = SQLQuerySpec(where=SshKeyFilters.with_user_id(1))
            query.enrich_stmt(statement)

    def test_sqlalchemy_setup_joins(self):
        stmt = select(A)
        joined_tables = [joined_table[0] for joined_table in stmt._setup_joins]
        assert joined_tables == []

        stmt = select(A).join(B, eq(A.c.b_id, B.c.id))
        joined_tables = [joined_table[0] for joined_table in stmt._setup_joins]
        assert joined_tables == [B]

        stmt = (
            select(A)
            .join(B, eq(A.c.b_id, B.c.id))
            .join(C, eq(C.c.id, B.c.c_id))
        )
        joined_tables = [joined_table[0] for joined_table in stmt._setup_joins]
        assert joined_tables == [B, C]

    def test_sqlalchemy_where_criteria(self):
        stmt = update(A)
        assert stmt._where_criteria == ()

        cond1 = eq(A.c.id, 100)
        stmt = update(A).where(cond1)
        assert stmt._where_criteria == (cond1,)

        cond2 = eq(A.c.b_id, B.c.id)
        stmt = update(A).where(cond1).where(cond2)
        assert stmt._where_criteria == (cond1, cond2)

        cond3 = eq(B.c.c_id, C.c.id)
        stmt = update(A).where(cond1).where(cond2).where(cond3)
        assert stmt._where_criteria == (cond1, cond2, cond3)

        stmt = delete(A).where(cond1)
        assert stmt._where_criteria == (cond1,)

        stmt = delete(A).where(cond1).where(cond2)
        assert stmt._where_criteria == (cond1, cond2)

        stmt = delete(A).where(cond1).where(cond2).where(cond3)
        assert stmt._where_criteria == (cond1, cond2, cond3)
