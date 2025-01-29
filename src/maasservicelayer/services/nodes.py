#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.nodes import (
    AbstractNodesRepository,
    NodeClauseFactory,
)
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.nodes import Node, NodeBuilder
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.secrets import SecretsService


class NodesService(BaseService[Node, AbstractNodesRepository, NodeBuilder]):
    def __init__(
        self,
        context: Context,
        secrets_service: SecretsService,
        nodes_repository: AbstractNodesRepository,
    ):
        super().__init__(context, nodes_repository)
        self.secrets_service = secrets_service

    async def update_by_system_id(
        self, system_id: str, builder: NodeBuilder
    ) -> Node:
        return await self.repository.update_one(
            query=QuerySpec(where=NodeClauseFactory.with_system_id(system_id)),
            builder=builder,
        )

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        """
        Move all the Nodes from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.repository.move_to_zone(old_zone_id, new_zone_id)

    async def move_bmcs_to_zone(
        self, old_zone_id: int, new_zone_id: int
    ) -> None:
        """
        Move all the BMC from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.repository.move_bmcs_to_zone(
            old_zone_id, new_zone_id
        )

    async def get_bmc(self, system_id: str) -> Bmc | None:
        bmc = await self.repository.get_node_bmc(system_id)
        if bmc is not None:
            secret_power_params = (
                await self.secrets_service.get_composite_secret(
                    f"bmc/{bmc.id}/power_parameters"
                )
            )
            bmc.power_parameters.update(secret_power_params)
        return bmc

    async def hostname_exists(self, hostname: str) -> bool:
        return await self.repository.hostname_exists(hostname)

    async def get_nodes_for_user(self, user_id: int) -> list[Node]:
        return await self.get_many(
            query=QuerySpec(where=NodeClauseFactory.with_owner_id(user_id))
        )
