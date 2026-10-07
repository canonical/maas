#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.nodeuserdata import NodeUserDataBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.nodeuserdata import (
    NodeUserDataClauseFactory,
    NodeUserDataRepository,
)
from maasservicelayer.models.nodeuserdata import NodeUserData
from maasservicelayer.services.base import BaseService


class NodeUserDataService(
    BaseService[NodeUserData, NodeUserDataRepository, NodeUserDataBuilder]
):
    def __init__(
        self, context: Context, nodeuserdata_repository: NodeUserDataRepository
    ):
        super().__init__(context, nodeuserdata_repository)

    async def set_user_data_for_ephemeral_env(
        self, node_id: int, data: bytes | None
    ) -> None:
        if data is None:
            await self._remove(node_id, for_ephemeral=True)
        else:
            await self._set(node_id, data, for_ephemeral=True)

    async def get_user_data_for_ephemeral_env(
        self, node_id: int
    ) -> bytes | None:
        return await self._get(node_id, for_ephemeral=True)

    async def _get(self, node_id: int, for_ephemeral: bool) -> bytes | None:
        entry = await self.get_one(
            query=self._query_for(node_id, for_ephemeral)
        )
        return entry.data if entry else None

    async def _set(
        self, node_id: int, data: bytes, for_ephemeral: bool
    ) -> None:
        await self.repository.upsert(
            NodeUserDataBuilder(
                node_id=node_id,
                data=data,
                for_ephemeral_environment=for_ephemeral,
            )
        )

    async def _remove(self, node_id: int, for_ephemeral: bool) -> None:
        """Delete the node user data entry for a node and environment."""
        # The unique constraint on (node_id, for_ephemeral_environment)
        # ensures at most one entry. Use delete_many so no error is raised
        # if no entry exists yet.
        await self.delete_many(query=self._query_for(node_id, for_ephemeral))

    def _query_for(self, node_id: int, for_ephemeral: bool) -> QuerySpec:
        return QuerySpec(
            where=NodeUserDataClauseFactory.and_clauses(
                [
                    NodeUserDataClauseFactory.with_node_id(node_id),
                    NodeUserDataClauseFactory.with_for_ephemeral_environment(
                        for_ephemeral
                    ),
                ]
            )
        )
