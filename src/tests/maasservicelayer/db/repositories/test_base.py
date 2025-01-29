#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

import pytest
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    join,
    MetaData,
    Table,
    Text,
)
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db import Database
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    MultipleResultsException,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.base import MaasTimestampedBaseModel, make_builder
from maasservicelayer.utils.date import utcnow

METADATA = MetaData()

A = Table(
    "test_table_a",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("data", Text),
    Column("b_id", BigInteger, ForeignKey("test_table_b.id"), nullable=False),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
)

B = Table(
    "test_table_b",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("c_id", BigInteger, ForeignKey("test_table_c.id")),
)

C = Table(
    "test_table_c",
    METADATA,
    Column("id", BigInteger, primary_key=True),
)


@pytest.fixture(autouse=True)
async def setup(db: Database):
    async with db.engine.begin() as conn:
        await conn.run_sync(METADATA.drop_all)
        await conn.run_sync(METADATA.create_all)
        now = utcnow()
        await conn.execute(
            C.insert(),
            [
                {"id": 1, "created": now, "updated": now},
                {"id": 2, "created": now, "updated": now},
                {"id": 3, "created": now, "updated": now},
            ],
        )
        await conn.execute(
            B.insert(),
            [{"id": 1, "c_id": 1}, {"id": 2, "c_id": 2}, {"id": 3, "c_id": 3}],
        )
        await conn.execute(
            A.insert(),
            [
                {
                    "id": 1,
                    "data": "foo",
                    "b_id": 1,
                    "created": now,
                    "updated": now,
                },
                {
                    "id": 2,
                    "data": "boo",
                    "b_id": 1,
                    "created": now,
                    "updated": now,
                },
            ],
        )
    yield
    async with db.engine.begin() as conn:
        await conn.run_sync(METADATA.drop_all)


class AModel(MaasTimestampedBaseModel):
    id: int
    data: str


AResourceBuilder = make_builder(AModel)


class MyRepository(BaseRepository[AModel]):
    def get_repository_table(self) -> Table:
        return A

    def get_model_factory(self) -> Type[AModel]:
        return AModel


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestMyRepository:
    async def test_exists(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        exists = await repo.exists(QuerySpec(where=Clause(eq(A.c.id, 1))))
        assert exists is True

    async def test_dont_exist(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        exists = await repo.exists(QuerySpec(where=Clause(eq(A.c.id, 0))))
        assert exists is False

    async def test_get_many(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        a_objs = await repo.get_many(QuerySpec())
        assert len(a_objs) == 2

    async def test_get_one(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        query = QuerySpec(
            where=Clause(
                condition=eq(A.c.data, "foo"),
                joins=[join(A, B, eq(A.c.b_id, B.c.id))],
            )
        )
        a_obj = await repo.get_one(query)
        assert a_obj is not None
        assert a_obj.id == 1
        assert a_obj.data == "foo"

    async def test_get_one_multiple_results(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        with pytest.raises(MultipleResultsException):
            await repo.get_one(QuerySpec())

    async def test_get_one_not_found(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        a_obj = await repo.get_one(QuerySpec(where=Clause(eq(A.c.id, 0))))
        assert a_obj is None

    async def test_get_by_id(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        a_obj = await repo.get_by_id(1)
        assert a_obj is not None
        assert a_obj.id == 1
        assert a_obj.data == "foo"

    async def test_get_by_id_not_found(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        a_obj = await repo.get_by_id(0)
        assert a_obj is None

    async def test_get_multiple_joins(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        query = QuerySpec(
            where=ClauseFactory.and_clauses(
                [
                    Clause(
                        condition=eq(A.c.data, "foo"),
                        joins=[join(A, B, eq(A.c.b_id, B.c.id))],
                    ),
                    Clause(
                        condition=eq(A.c.data, "foo"),
                        joins=[join(B, C, eq(B.c.c_id, C.c.id))],
                    ),
                ]
            )
        )
        a_obj = await repo.get_one(query)
        assert a_obj is not None
        assert a_obj.id == 1
        assert a_obj.data == "foo"

    async def test_update_one(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        builder = AResourceBuilder(data="test")
        query = QuerySpec(
            where=Clause(
                condition=eq(A.c.data, "foo"),
                joins=[join(A, B, eq(A.c.b_id, B.c.id))],
            )
        )
        updated_obj = await repo.update_one(query=query, builder=builder)
        assert updated_obj is not None
        assert updated_obj.data == "test"

    async def test_update_one_multiple_matches(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        builder = AResourceBuilder(data="test")
        query = QuerySpec()
        with pytest.raises(MultipleResultsException):
            await repo.update_one(query=query, builder=builder)

    async def test_update_one_no_matches(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        builder = AResourceBuilder(data="test")
        query = QuerySpec(
            where=Clause(condition=eq(A.c.data, "definitely_not_a_match"))
        )
        with pytest.raises(NotFoundException):
            await repo.update_one(query=query, builder=builder)

    async def test_update_by_id_no_matches(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        builder = AResourceBuilder(data="test")
        with pytest.raises(NotFoundException):
            await repo.update_by_id(0, builder=builder)

    async def test_update_one_multiple_joins(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        builder = AResourceBuilder(data="test")
        query = QuerySpec(
            where=ClauseFactory.and_clauses(
                [
                    Clause(
                        condition=eq(A.c.data, "foo"),
                        joins=[join(A, B, eq(A.c.b_id, B.c.id))],
                    ),
                    Clause(
                        condition=eq(A.c.data, "foo"),
                        joins=[join(B, C, eq(B.c.c_id, C.c.id))],
                    ),
                ]
            )
        )
        updated_obj = await repo.update_one(query=query, builder=builder)
        assert updated_obj is not None
        assert updated_obj.data == "test"

    async def test_update_many(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        builder = AResourceBuilder(data="test")
        resources = await repo.update_many(QuerySpec(), builder=builder)
        assert len(resources) == 2
        assert all(resource.data == "test" for resource in resources)

    async def test_delete_one(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        query = QuerySpec(
            where=Clause(
                condition=eq(A.c.data, "foo"),
                joins=[join(A, B, eq(A.c.b_id, B.c.id))],
            )
        )
        deleted_resource = await repo.delete_one(query=query)
        assert deleted_resource.id == 1
        deleted_obj = await repo.get_one(query=query)
        assert deleted_obj is None

    async def test_delete_one_no_match(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        query = QuerySpec(
            where=Clause(
                condition=eq(A.c.data, "definitely not a match"),
            )
        )
        deleted_resource = await repo.delete_one(query=query)
        assert deleted_resource is None
        deleted_obj = await repo.get_one(query=query)
        assert deleted_obj is None

    async def test_delete_by_id(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        deleted_resource = await repo.delete_by_id(1)
        assert deleted_resource.id == 1
        deleted_obj = await repo.get_by_id(1)
        assert deleted_obj is None

    async def test_delete_multiple_joins(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        query = QuerySpec(
            where=ClauseFactory.and_clauses(
                [
                    Clause(
                        condition=eq(A.c.data, "foo"),
                        joins=[join(A, B, eq(A.c.b_id, B.c.id))],
                    ),
                    Clause(
                        condition=eq(A.c.data, "foo"),
                        joins=[join(B, C, eq(B.c.c_id, C.c.id))],
                    ),
                ]
            )
        )
        await repo.delete_one(query=query)
        deleted_obj = await repo.delete_one(query=query)
        assert deleted_obj is None

    async def test_delete_many(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        deleted_resources = await repo.delete_many(QuerySpec())
        assert len(deleted_resources) == 2
