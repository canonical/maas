#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import (
    BigInteger,
    Column,
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

from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec

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
                Clause(condition=literal(1), joins=None),
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
    def test_enrich_stmt_select(self):
        stmt = select(A.c.id)
        query = QuerySpec(
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

    def test_enrich_stmt_update(self):
        stmt = update(A).values(id=100)
        query = QuerySpec(
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

    def test_enrich_stmt_delete(self):
        stmt = delete(A).where(A.c.id < 3)
        query = QuerySpec(
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

    def test_enrich_stmt_select_multiple_joins(self):
        stmt = select(A.c.id)
        query = QuerySpec(
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
        query = QuerySpec(
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
        query = QuerySpec(
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
        query = QuerySpec(
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
            == "SELECT test_table_a.id FROM test_table_a JOIN test_table_b ON test_table_a.b_id = test_table_b.id WHERE test_table_b.id = 1 AND test_table_b.id = 2"
        )

    def test_enrich_stmt_select_update_redundant_joins(self):
        stmt = update(A).values(id=100)
        query = QuerySpec(
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

    def test_enrich_stmt_select_delete_redundant_joins(self):
        stmt = delete(A).where(A.c.id < 3)
        query = QuerySpec(
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
