#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert

from maasservicelayer.builders.nodeuserdata import NodeUserDataBuilder
from maasservicelayer.db.mappers.base import BaseDomainDataMapper
from maasservicelayer.db.mappers.nodeuserdata import (
    NodeUserDataDomainDataMapper,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import NodeUserDataTable
from maasservicelayer.models.nodeuserdata import NodeUserData


class NodeUserDataRepository(BaseRepository[NodeUserData]):
    def get_repository_table(self) -> Table:
        return NodeUserDataTable

    def get_model_factory(self) -> type[NodeUserData]:
        return NodeUserData

    def get_mapper(self) -> BaseDomainDataMapper[NodeUserData]:
        return NodeUserDataDomainDataMapper(
            NodeUserData, self.get_repository_table()
        )

    async def upsert(self, builder: NodeUserDataBuilder) -> NodeUserData:
        resource = self.mapper.build_resource(builder)
        stmt = insert(NodeUserDataTable).values(**resource.get_values())
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[
                NodeUserDataTable.c.node_id,
                NodeUserDataTable.c.for_ephemeral_environment,
            ],
            set_=resource.get_values(),
        ).returning(NodeUserDataTable)

        result = (await self.execute_stmt(upsert_stmt)).one()
        return self.mapper.to_domain(result._mapping)

    # The following methods are intentionally not implemented, `upsert`
    # should be used instead of the standard create/update methods.
    #
    # List operations remain intentionally unsupported.
    async def list(self, page, size, query=None):
        raise NotImplementedError("List is not supported for node user data.")

    async def list_all(self, query=None):
        raise NotImplementedError("List is not supported for node user data.")

    async def create(self, builder):
        raise NotImplementedError(
            "Create is not supported for node user data. Use `upsert`."
        )

    async def create_many(self, builders):
        raise NotImplementedError(
            "Create is not supported for node user data. Use `upsert`."
        )

    async def update_one(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for node user data. Use `upsert`."
        )

    async def update_many(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for node user data. Use `upsert`."
        )

    async def update_by_id(self, id, builder):
        raise NotImplementedError(
            "Update is not supported for node user data. Use `upsert`."
        )

    async def _update(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for node user data. Use `upsert`."
        )
