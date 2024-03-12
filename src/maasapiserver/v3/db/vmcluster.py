from sqlalchemy import update
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db.tables import VmClusterTable
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.api.models.requests.vmcluster import VmClusterRequest
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.vmcluster import VmCluster


class VmClustersRepository(BaseRepository[VmCluster, VmClusterRequest]):
    async def create(self, request: VmClusterRequest) -> VmCluster:
        raise Exception("Not implemented yet.")

    async def find_by_id(self, id: int) -> VmCluster | None:
        raise Exception("Not implemented yet.")

    async def list(
        self, pagination_params: PaginationParams
    ) -> ListResult[VmCluster]:
        raise Exception("Not implemented yet.")

    async def update(self, resource: VmCluster) -> VmCluster:
        raise Exception("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise Exception("Not implemented yet.")

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        stmt = (
            update(VmClusterTable)
            .where(eq(VmClusterTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.connection.execute(stmt)
