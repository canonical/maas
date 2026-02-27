# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import delete, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.operators import eq

from maascommon.enums.openfga import OPENFGA_STORE_ID
from maascommon.utils.ulid import generate_ulid
from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.mappers.base import (
    BaseDomainDataMapper,
    CreateOrUpdateResource,
)
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import OpenFGATupleTable
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
)
from maasservicelayer.exceptions.constants import (
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.openfga_tuple import OpenFGATuple
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

    async def create(self, builder: OpenFGATupleBuilder) -> OpenFGATuple:
        resource = self.get_mapper().build_resource(builder)

        # Populate the store, inserted_at and ulid automatically.
        resource["store"] = OPENFGA_STORE_ID
        resource["inserted_at"] = utcnow()
        resource["ulid"] = generate_ulid()

        stmt = (
            insert(OpenFGATupleTable)
            .returning(OpenFGATupleTable)
            .values(**resource.get_values())
        )
        try:
            result = (await self.execute_stmt(stmt)).one()
            result_dict = result._asdict()
            result_dict["user"] = result_dict["_user"]
            return OpenFGATuple(**result_dict)
        except IntegrityError as e:
            raise AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                        message="A resource with such identifiers already exist.",
                    )
                ]
            ) from e

    async def delete_many(self, query: QuerySpec) -> None:
        stmt = delete(OpenFGATupleTable).returning(OpenFGATupleTable)
        stmt = query.enrich_stmt(stmt)
        await self.execute_stmt(stmt)
