# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import select, Table

from maascommon.enums.package_repositories import (
    PACKAGE_REPO_MAIN_ARCHES,
    PACKAGE_REPO_PORTS_ARCHES,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import PackageRepositoryTable
from maasservicelayer.models.package_repositories import PackageRepository


class PackageRepositoriesRepository(BaseRepository[PackageRepository]):
    def get_repository_table(self) -> Table:
        return PackageRepositoryTable

    def get_model_factory(self) -> type[PackageRepository]:
        return PackageRepository

    async def get_main_archive(self) -> PackageRepository:
        stmt = select(PackageRepositoryTable).where(
            PackageRepositoryTable.c.arches.contains(PACKAGE_REPO_MAIN_ARCHES),
            eq(PackageRepositoryTable.c.enabled, True),
            eq(PackageRepositoryTable.c.default, True),
        )
        result = await self.execute_stmt(stmt)
        # The main archive is always present
        package_repo = result.one()
        return PackageRepository(**package_repo._asdict())

    async def get_ports_archive(self) -> PackageRepository:
        stmt = select(PackageRepositoryTable).where(
            PackageRepositoryTable.c.arches.contains(
                PACKAGE_REPO_PORTS_ARCHES
            ),
            eq(PackageRepositoryTable.c.enabled, True),
            eq(PackageRepositoryTable.c.default, True),
        )
        result = await self.execute_stmt(stmt)
        # The ports archive is always present
        package_repo = result.one()
        return PackageRepository(**package_repo._asdict())
