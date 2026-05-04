# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import delete, desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.operators import eq
from ulid import ULID

from maascommon.enums.openfga import OPENFGA_STORE_ID
from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.mappers.base import (
    BaseDomainDataMapper,
    CreateOrUpdateResource,
)
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import OpenFGATupleTable
from maasservicelayer.models.base import ListResult, ResourceBuilder
from maasservicelayer.models.openfga_tuple import (
    EntitlementDeleteSpec,
    OpenFGATuple,
)
from maasservicelayer.utils.date import utcnow


class OpenFGATuplesClauseFactory(ClauseFactory):
    @classmethod
    def with_object_type(cls, object_type: str) -> Clause:
        return Clause(
            condition=eq(OpenFGATupleTable.c.object_type, object_type)
        )

    @classmethod
    def with_object_id(cls, object_id: str) -> Clause:
        return Clause(condition=eq(OpenFGATupleTable.c.object_id, object_id))

    @classmethod
    def with_relation(cls, relation: str) -> Clause:
        return Clause(condition=eq(OpenFGATupleTable.c.relation, relation))

    @classmethod
    def with_user(cls, user: str) -> Clause:
        return Clause(condition=eq(OpenFGATupleTable.c._user, user))

    @classmethod
    def with_users(cls, users: list[str]) -> Clause:
        return Clause(condition=OpenFGATupleTable.c._user.in_(users))

    @classmethod
    def with_entitlement_tuples(
        cls, specs: list[EntitlementDeleteSpec]
    ) -> Clause:
        return cls.or_clauses(
            [
                cls.and_clauses(
                    [
                        cls.with_relation(spec.entitlement),
                        cls.with_object_type(spec.resource_type),
                        cls.with_object_id(str(spec.resource_id)),
                    ]
                )
                for spec in specs
            ]
        )


class OpenFGATuplesDataMapper(BaseDomainDataMapper):
    def __init__(self):
        super().__init__(OpenFGATupleTable)

    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        resource = CreateOrUpdateResource()

        populated_fields = builder.populated_fields()
        if "user" in populated_fields:
            populated_fields["_user"] = populated_fields.pop("user")

        for name, value in populated_fields.items():
            resource.set_value(self.table_columns[name].name, value)

        return resource


class OpenFGATuplesRepository(Repository):
    def get_mapper(self) -> BaseDomainDataMapper:
        return OpenFGATuplesDataMapper()

    async def get_many(self, query: QuerySpec) -> list[OpenFGATuple]:
        stmt = select(OpenFGATupleTable).select_from(OpenFGATupleTable)
        stmt = query.enrich_stmt(stmt)
        result = await self.execute_stmt(stmt)
        items = []
        for row in result:
            row_asdict = row._asdict()
            row_asdict["user"] = row_asdict.pop("_user")
            items.append(OpenFGATuple(**row_asdict))
        return items

    async def upsert(self, builder: OpenFGATupleBuilder) -> OpenFGATuple:
        resource = self.get_mapper().build_resource(builder)

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
        result_dict = result._asdict()

        result_dict["user"] = result_dict.pop("_user")
        return OpenFGATuple(**result_dict)

    async def bulk_upsert(self, builders: list[OpenFGATupleBuilder]) -> None:
        if not builders:
            return
        new_timestamp = utcnow()
        values_list = [
            {
                **self.get_mapper().build_resource(builder).get_values(),
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
        stmt = query.enrich_stmt(stmt)
        await self.execute_stmt(stmt)

    async def list_entitlements(
        self, page: int, size: int, query: QuerySpec
    ) -> ListResult[OpenFGATuple]:
        total_stmt = select(count()).select_from(OpenFGATupleTable)
        total_stmt = query.enrich_stmt(total_stmt)
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = (
            select(OpenFGATupleTable)
            .select_from(OpenFGATupleTable)
            .order_by(desc(OpenFGATupleTable.c.inserted_at))
            .offset((page - 1) * size)
            .limit(size)
        )
        stmt = query.enrich_stmt(stmt)
        result = await self.execute_stmt(stmt)
        items = []
        for row in result:
            row_asdict = row._asdict()
            row_asdict["user"] = row_asdict.pop("_user")
            items.append(OpenFGATuple(**row_asdict))
        return ListResult(items=items, total=total)
