#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasservicelayer.db.repositories.vmcluster import VmClustersRepository


class VmClustersService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        vmcluster_repository: VmClustersRepository | None = None,
    ):
        super().__init__(connection)
        self.vmcluster_repository = (
            vmcluster_repository
            if vmcluster_repository
            else VmClustersRepository(connection)
        )

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        """
        Move all the VMClusters from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.vmcluster_repository.move_to_zone(
            old_zone_id, new_zone_id
        )
