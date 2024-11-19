#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.vmcluster import VmClustersRepository
from maasservicelayer.services._base import Service


class VmClustersService(Service):
    def __init__(
        self,
        context: Context,
        vmcluster_repository: VmClustersRepository | None = None,
    ):
        super().__init__(context)
        self.vmcluster_repository = (
            vmcluster_repository
            if vmcluster_repository
            else VmClustersRepository(context)
        )

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        """
        Move all the VMClusters from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.vmcluster_repository.move_to_zone(
            old_zone_id, new_zone_id
        )
