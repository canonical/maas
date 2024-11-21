from operator import eq
from typing import Type

import pytest
from sqlalchemy import (
    BigInteger,
    Column,
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
    ResourceBuilder,
)
from maasservicelayer.models.base import MaasTimestampedBaseModel

METADATA = MetaData()

A = Table(
    "test_table_a",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("data", Text),
    Column("b_id", BigInteger, ForeignKey("test_table_b.id"), nullable=False),
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
        await conn.execute(C.insert(), [{"id": 1}, {"id": 2}, {"id": 3}])
        await conn.execute(
            B.insert(),
            [{"id": 1, "c_id": 1}, {"id": 2, "c_id": 2}, {"id": 3, "c_id": 3}],
        )
        await conn.execute(A.insert(), [{"id": 1, "data": "foo", "b_id": 1}])
    yield
    async with db.engine.begin() as conn:
        await conn.run_sync(METADATA.drop_all)


class AModel(MaasTimestampedBaseModel):
    id: int
    data: str


class AResourceBuilder(ResourceBuilder):
    def with_data(self, data: str) -> "AResourceBuilder":
        self._request.set_value("data", data)
        return self


class MyRepository(BaseRepository[AModel]):
    def get_repository_table(self) -> Table:
        return A

    def get_model_factory(self) -> Type[AModel]:
        return AModel


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestMyRepository:
    async def test_get(self, db_connection: AsyncConnection) -> None:
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

    async def test_update(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        builder = AResourceBuilder().with_data("test")
        query = QuerySpec(
            where=Clause(
                condition=eq(A.c.data, "foo"),
                joins=[join(A, B, eq(A.c.b_id, B.c.id))],
            )
        )
        updated_obj = await repo.update(query=query, resource=builder.build())
        assert updated_obj is not None
        assert updated_obj.data == "test"

    async def test_update_multiple_joins(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        builder = AResourceBuilder().with_data("test")
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
        updated_obj = await repo.update(query=query, resource=builder.build())
        assert updated_obj is not None
        assert updated_obj.data == "test"

    async def test_delete(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        query = QuerySpec(
            where=Clause(
                condition=eq(A.c.data, "foo"),
                joins=[join(A, B, eq(A.c.b_id, B.c.id))],
            )
        )
        await repo.delete(query=query)
        deleted_obj = await repo.get_one(query=query)
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
        await repo.delete(query=query)
        deleted_obj = await repo.delete(query=query)
        assert deleted_obj is None
