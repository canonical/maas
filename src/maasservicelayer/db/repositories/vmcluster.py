#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import update
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import FilterQuery
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
)
from maasservicelayer.db.tables import VmClusterTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.vmcluster import VmCluster


class VmClustersRepository(BaseRepository[VmCluster]):
    async def create(self, resource: CreateOrUpdateResource) -> VmCluster:
        raise NotImplementedError("Not implemented yet.")

    async def find_by_id(self, id: int) -> VmCluster | None:
        raise NotImplementedError("Not implemented yet.")

    async def list(
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[VmCluster]:
        raise Exception("Not implemented yet.")

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> VmCluster:
        raise NotImplementedError("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        stmt = (
            update(VmClusterTable)
            .where(eq(VmClusterTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.connection.execute(stmt)
