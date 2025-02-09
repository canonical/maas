#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from typing import Type

from sqlalchemy import Table, update
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import VmClusterTable
from maasservicelayer.models.vmcluster import VmCluster


class VmClustersRepository(BaseRepository[VmCluster]):
    def get_repository_table(self) -> Table:
        return VmClusterTable

    def get_model_factory(self) -> Type[VmCluster]:
        return VmCluster

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        stmt = (
            update(VmClusterTable)
            .where(eq(VmClusterTable.c.zone_id, old_zone_id))
            .values(zone_id=new_zone_id)
        )
        await self.execute_stmt(stmt)
