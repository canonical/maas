#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode
from operator import eq
from typing import Any, List

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert

from maasservicelayer.builders.nodeuserdata import NodeUserDataBuilder
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
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
    """Note: `delete_*` methods return models with `data` still
    base64-encoded from the mapper; decode it before use if you need
    the deleted content."""

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
        return self._to_model(result._asdict())

    async def _get(self, query: QuerySpec) -> List[NodeUserData]:
        """
        This override is required to convert the string-based,
        base64-encoded data that the database uses, to a valid `bytes`
        representation used by the domain (service layer) model.

        This is called by `get_one`, `get_by_id`, and `get_many`.
        """
        stmt = self.select_all_statement()
        stmt = query.enrich_stmt(stmt)

        result = (await self.execute_stmt(stmt)).all()
        return [self._to_model(row._asdict()) for row in result]

    def _to_model(self, row: dict[str, Any]) -> NodeUserData:
        """`data` is stored base64-encoded - decode it to bytes for the
        domain model."""
        row["data"] = b64decode(row["data"])
        return self.get_model_factory()(**row)

    # The following methods are intentionally not implemented, `upsert`
    # should be used instead of the standard create/update methods.
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
