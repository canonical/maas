from base64 import b64decode
from operator import eq

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert

from maasservicelayer.builders.nodeuserdata import NodeUserDataBuilder
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.mappers.base import BaseDomainDataMapper
from maasservicelayer.db.mappers.nodeuserdata import (
    NodeUserDataDomainDataMapper,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import NodeUserDataTable
from maasservicelayer.models.nodeuserdata import NodeUserData


class NodeUserDataClauseFactory(ClauseFactory):
    @classmethod
    def with_node_id(cls, node_id: int) -> Clause:
        return Clause(condition=eq(NodeUserDataTable.c.node_id, node_id))

    @classmethod
    def with_for_ephemeral_environment(cls, for_ephemeral: bool) -> Clause:
        return Clause(
            condition=eq(
                NodeUserDataTable.c.for_ephemeral_environment, for_ephemeral
            )
        )


class NodeUserDataRepository(BaseRepository[NodeUserData]):
    def get_repository_table(self) -> Table:
        return NodeUserDataTable

    def get_model_factory(self) -> type[NodeUserData]:
        return NodeUserData

    def get_mapper(self) -> BaseDomainDataMapper:
        return NodeUserDataDomainDataMapper(self.get_repository_table())

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
        # The mapper encodes data during `build_resource`, we need to decode it here to
        # return the correct `data` type in the domain model.
        row = result._asdict()
        row["data"] = b64decode(row["data"])
        return NodeUserData(**row)
