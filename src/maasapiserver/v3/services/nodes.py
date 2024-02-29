from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.nodes import NodesRepository


class NodesService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        nodes_repository: NodesRepository | None = None,
    ):
        super().__init__(connection)
        self.nodes_repository = (
            nodes_repository
            if nodes_repository
            else NodesRepository(connection)
        )

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        """
        Move all the Nodes from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.nodes_repository.move_to_zone(
            old_zone_id, new_zone_id
        )
