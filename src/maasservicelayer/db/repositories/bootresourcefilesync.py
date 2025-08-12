# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the filesync LICENSE).


from operator import eq

from sqlalchemy import func, select, Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    BootResourceFileSyncTable,
    BootResourceFileTable,
    NodeTable,
)
from maasservicelayer.models.bootresourcefilesync import BootResourceFileSync


class BootResourceFileSyncClauseFactory(ClauseFactory):
    @classmethod
    def with_file_id(cls, file_id: int) -> Clause:
        return Clause(
            condition=eq(BootResourceFileSyncTable.c.file_id, file_id)
        )

    @classmethod
    def with_file_ids(cls, file_ids: set[int]) -> Clause:
        return Clause(
            condition=BootResourceFileSyncTable.c.file_id.in_(file_ids)
        )


class BootResourceFileSyncRepository(BaseRepository[BootResourceFileSync]):
    def get_repository_table(self) -> Table:
        return BootResourceFileSyncTable

    def get_model_factory(self) -> type[BootResourceFileSync]:
        return BootResourceFileSync

    async def get_current_sync_size_for_files(self, file_ids: set[int]) -> int:
        """Calculate the current synchronized size of the files that match the ids."""
        stmt = (
            select(
                func.coalesce(func.sum(BootResourceFileSyncTable.c.size), 0)
            )
            .select_from(BootResourceFileSyncTable)
            .where(BootResourceFileSyncTable.c.file_id.in_(file_ids))
        )

        return (await self.execute_stmt(stmt)).scalar_one()

    async def get_synced_regions_for_file(self, file_id: int) -> list[str]:
        """Returns the system ids of the regions that have a full copy of the file with the specified id."""
        stmt = (
            select(NodeTable.c.system_id)
            .distinct()
            .select_from(NodeTable)
            .join(
                BootResourceFileSyncTable,
                eq(
                    NodeTable.c.id,
                    BootResourceFileSyncTable.c.region_id,
                ),
            )
            .join(
                BootResourceFileTable,
                eq(
                    BootResourceFileSyncTable.c.file_id,
                    BootResourceFileTable.c.id,
                ),
            )
            .where(eq(BootResourceFileTable.c.id, file_id))
            .where(
                eq(
                    BootResourceFileTable.c.size,
                    BootResourceFileSyncTable.c.size,
                )
            )
        )

        result = (await self.execute_stmt(stmt)).all()
        return [row[0] for row in result]
