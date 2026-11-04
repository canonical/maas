# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import datetime
from operator import eq
from typing import Type

from pydantic import Field
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
from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    MultipleResultsException,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
    Operator,
)
from maasservicelayer.filters.query import OrderBy, QuerySpec
from maasservicelayer.models.base import (
    MaasTimestampedBaseModel,
    ResourceBuilder,
    UNSET,
    Unset,
)
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


@dataclass(frozen=True)
class WithRelatedData(CustomFilter):
    model = AModel
    value: str
    include_c: bool = False


class AMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter):
        if isinstance(filter, WithRelatedData):
            joins = [join(A, B, eq(A.c.b_id, B.c.id))]
            if filter.include_c:
                joins.append(join(B, C, eq(B.c.c_id, C.c.id)))
            return Clause(condition=A.c.data == filter.value, joins=joins)
        return super().custom_filter_clause(filter)


class AResourceBuilder(ResourceBuilder):
    id: int | Unset = Field(default=UNSET)
    created: datetime | Unset = Field(default=UNSET)
    updated: datetime | Unset = Field(default=UNSET)
    data: str | Unset = Field(default=UNSET)


class MyRepository(BaseRepository[AModel]):
    def get_repository_table(self) -> Table:
        return A

    def get_model_factory(self) -> Type[AModel]:
        return AModel

    def get_mapper(self):
        return AMapper(AModel, A)


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestMyRepository:
    async def test_exists(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        exists = await repo.exists(
            QuerySpec(where=FieldFilter(AModel, "id", Operator.EQ, 1))
        )
        assert exists is True

    async def test_dont_exist(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        exists = await repo.exists(
            QuerySpec(where=FieldFilter(AModel, "id", Operator.EQ, 0))
        )
        assert exists is False

    async def test_get_many(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        a_objs = await repo.get_many(QuerySpec())
        assert len(a_objs) == 2

    async def test_get_one(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        query = QuerySpec(where=WithRelatedData("foo"))
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
        a_obj = await repo.get_one(
            QuerySpec(where=FieldFilter(AModel, "id", Operator.EQ, 0))
        )
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
            where=FilterFactory.and_filters(
                [
                    WithRelatedData("foo"),
                    WithRelatedData("foo", include_c=True),
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
        query = QuerySpec(where=WithRelatedData("foo"))
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
            where=FieldFilter(
                AModel, "data", Operator.EQ, "definitely_not_a_match"
            )
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
            where=FilterFactory.and_filters(
                [
                    WithRelatedData("foo"),
                    WithRelatedData("foo", include_c=True),
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
        query = QuerySpec(where=WithRelatedData("foo"))
        deleted_resource = await repo.delete_one(query=query)
        assert deleted_resource.id == 1
        deleted_obj = await repo.get_one(query=query)
        assert deleted_obj is None

    async def test_delete_one_no_match(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        query = QuerySpec(
            where=FieldFilter(
                AModel, "data", Operator.EQ, "definitely not a match"
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
            where=FilterFactory.and_filters(
                [
                    WithRelatedData("foo"),
                    WithRelatedData("foo", include_c=True),
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

    async def test_list_all(self, db_connection: AsyncConnection) -> None:
        repo = MyRepository(Context(connection=db_connection))
        resources = await repo.list_all()
        assert len(resources) == 2

    async def test_list_all_with_query(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        resources = await repo.list_all(
            query=QuerySpec(FieldFilter(AModel, "data", Operator.EQ, "foo"))
        )
        assert len(resources) == 1

    async def test_list_orders_items_without_ordering_the_count(
        self, db_connection: AsyncConnection
    ) -> None:
        repo = MyRepository(Context(connection=db_connection))
        result = await repo.list(
            page=1,
            size=1,
            query=QuerySpec(order_by=(OrderBy(AModel, "id"),)),
        )
        assert result.total == 2
        assert [resource.id for resource in result.items] == [1]
