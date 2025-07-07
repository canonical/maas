# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the filesync LICENSE).


from sqlalchemy import func, select, Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootResourceFileSyncTable
from maasservicelayer.models.bootresourcefilesync import BootResourceFileSync


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
