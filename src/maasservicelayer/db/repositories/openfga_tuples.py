# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import delete, desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.functions import count
from ulid import ULID

from maascommon.enums.openfga import OPENFGA_STORE_ID
from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import SQLQuerySpec
from maasservicelayer.db.mappers.openfga_tuples import OpenFGATuplesDataMapper
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import OpenFGATupleTable
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.openfga_tuple import OpenFGATuple
from maasservicelayer.utils.date import utcnow


class OpenFGATuplesRepository(Repository[OpenFGATuple]):
    def __init__(self, context: Context):
        super().__init__(context)
        self.mapper = self.get_mapper()

    def get_mapper(self) -> OpenFGATuplesDataMapper:
        return OpenFGATuplesDataMapper()

    async def get_many(self, query: QuerySpec) -> list[OpenFGATuple]:
        stmt = self.mapper.select_statement()
        stmt = self._translate(query).enrich_stmt(stmt)
        result = await self.execute_stmt(stmt)
        return [self.mapper.to_domain(row._mapping) for row in result]

    async def upsert(self, builder: OpenFGATupleBuilder) -> OpenFGATuple:
        resource = self.mapper.build_resource(builder)

        new_timestamp = utcnow()
        new_ulid = str(ULID())

        values = {
            **resource.get_values(),
            "store": OPENFGA_STORE_ID,
            "inserted_at": new_timestamp,
            "ulid": new_ulid,
        }

        stmt = insert(OpenFGATupleTable).values(**values)

        stmt = stmt.on_conflict_do_update(
            index_elements=[
                "store",
                "object_type",
                "object_id",
                "relation",
                "_user",
            ],
            set_={
                "inserted_at": new_timestamp,
                "ulid": new_ulid,
            },
        ).returning(OpenFGATupleTable)

        result = (await self.execute_stmt(stmt)).one()
        return self.mapper.to_domain(result._mapping)

    async def bulk_upsert(self, builders: list[OpenFGATupleBuilder]) -> None:
        if not builders:
            return
        new_timestamp = utcnow()
        values_list = [
            {
                **self.mapper.build_resource(builder).get_values(),
                "store": OPENFGA_STORE_ID,
                "inserted_at": new_timestamp,
                "ulid": str(ULID()),
            }
            for builder in builders
        ]
        stmt = insert(OpenFGATupleTable).values(values_list)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                "store",
                "object_type",
                "object_id",
                "relation",
                "_user",
            ],
            set_={"inserted_at": new_timestamp},
        )
        await self.execute_stmt(stmt)

    async def delete_many(self, query: QuerySpec) -> None:
        stmt = delete(OpenFGATupleTable).returning(OpenFGATupleTable)
        stmt = self._translate(query).enrich_stmt(stmt)
        await self.execute_stmt(stmt)

    async def list_entitlements(
        self, page: int, size: int, query: QuerySpec
    ) -> ListResult[OpenFGATuple]:
        total_stmt = select(count()).select_from(OpenFGATupleTable)
        sql_query = self._translate(query)
        total_stmt = SQLQuerySpec(where=sql_query.where).enrich_stmt(
            total_stmt
        )
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = (
            self.mapper.select_statement()
            .order_by(desc(OpenFGATupleTable.c.inserted_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        stmt = sql_query.enrich_stmt(stmt)
        result = await self.execute_stmt(stmt)
        items = [self.mapper.to_domain(row._mapping) for row in result]
        return ListResult(items=items, total=total)
