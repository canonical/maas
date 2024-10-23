#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.nodes import NodesRepository
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.nodes import Node
from maasservicelayer.services._base import Service
from maasservicelayer.services.secrets import SecretsService


class NodesService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        secrets_service: SecretsService,
        nodes_repository: NodesRepository | None = None,
    ):
        super().__init__(connection)
        self.secrets_service = secrets_service
        self.nodes_repository = (
            nodes_repository
            if nodes_repository
            else NodesRepository(connection)
        )

    async def update_by_system_id(
        self, system_id: str, resource: CreateOrUpdateResource
    ) -> Node:
        return await self.nodes_repository.update_by_system_id(
            system_id=system_id, resource=resource
        )

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        """
        Move all the Nodes from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.nodes_repository.move_to_zone(
            old_zone_id, new_zone_id
        )

    async def move_bmcs_to_zone(
        self, old_zone_id: int, new_zone_id: int
    ) -> None:
        """
        Move all the BMC from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.nodes_repository.move_bmcs_to_zone(
            old_zone_id, new_zone_id
        )

    async def get_bmc(self, system_id: str) -> Bmc | None:
        bmc = await self.nodes_repository.get_node_bmc(system_id)
        if bmc is not None:
            secret_power_params = (
                await self.secrets_service.get_composite_secret(
                    f"bmc/{bmc.id}/power_parameters"
                )
            )
            bmc.power_parameters.update(secret_power_params)
        return bmc

    async def hostname_exists(self, hostname: str) -> bool:
        return await self.nodes_repository.hostname_exists(hostname)
