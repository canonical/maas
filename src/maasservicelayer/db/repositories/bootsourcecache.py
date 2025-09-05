# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import not_, select, Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootSourceCacheTable
from maasservicelayer.models.bootsourcecache import BootSourceCache


class BootSourceCacheClauseFactory(ClauseFactory):
    @classmethod
    def with_os(cls, os: str) -> Clause:
        return Clause(condition=eq(BootSourceCacheTable.c.os, os))

    @classmethod
    def with_arch(cls, arch: str) -> Clause:
        return Clause(condition=eq(BootSourceCacheTable.c.arch, arch))

    @classmethod
    def with_subarch(cls, subarch: str) -> Clause:
        return Clause(condition=eq(BootSourceCacheTable.c.subarch, subarch))

    @classmethod
    def with_release(cls, release: str) -> Clause:
        return Clause(condition=eq(BootSourceCacheTable.c.release, release))

    @classmethod
    def with_label(cls, label: str) -> Clause:
        return Clause(condition=eq(BootSourceCacheTable.c.label, label))

    @classmethod
    def with_kflavor(cls, kflavor: str | None) -> Clause:
        return Clause(condition=eq(BootSourceCacheTable.c.kflavor, kflavor))

    @classmethod
    def with_boot_source_id(cls, boot_source_id: int) -> Clause:
        return Clause(
            condition=eq(BootSourceCacheTable.c.boot_source_id, boot_source_id)
        )

    @classmethod
    def with_ids(cls, ids: set[int]) -> Clause:
        return Clause(condition=BootSourceCacheTable.c.id.in_(ids))


class BootSourceCacheRepository(BaseRepository[BootSourceCache]):
    def get_repository_table(self) -> Table:
        return BootSourceCacheTable

    def get_model_factory(self) -> type[BootSourceCache]:
        return BootSourceCache

    async def get_available_lts_releases(self) -> list[str]:
        """Get the LTS release names that are available in the boot source cache.

        Results are returned in descending order based on their "support_eol" date - latest first.

        Returns:
            A list of LTS release names, e.g. ["noble", "jammy"]
        """
        stmt = (
            select(
                BootSourceCacheTable.c.release,
                BootSourceCacheTable.c.support_eol,
            )
            .distinct()
            .select_from(BootSourceCacheTable)
            .where(not_(eq(BootSourceCacheTable.c.support_eol, None)))
            .where(BootSourceCacheTable.c.release_title.endswith("LTS"))
            .order_by(BootSourceCacheTable.c.support_eol.desc())
        )
        result = (await self.execute_stmt(stmt)).all()
        # keep only the releases
        return [row[0] for row in result]
