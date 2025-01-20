#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.vmcluster import VmClustersRepository
from maasservicelayer.models.vmcluster import VmCluster, VmClusterBuilder
from maasservicelayer.services._base import BaseService


class VmClustersService(
    BaseService[VmCluster, VmClustersRepository, VmClusterBuilder]
):
    def __init__(
        self, context: Context, vmcluster_repository: VmClustersRepository
    ):
        super().__init__(context, vmcluster_repository)

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        """
        Move all the VMClusters from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.repository.move_to_zone(old_zone_id, new_zone_id)
