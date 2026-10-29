# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import List

from sqlalchemy import desc, Table

from maasservicelayer.db.mappers.bootresourcesets import (
    BootResourceSetDomainDataMapper,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootResourceSetTable
from maasservicelayer.models.bootresourcesets import BootResourceSet


class BootResourceSetsRepository(BaseRepository[BootResourceSet]):
    def get_mapper(self) -> BootResourceSetDomainDataMapper:
        return BootResourceSetDomainDataMapper(
            BootResourceSet, BootResourceSetTable
        )

    def get_repository_table(self) -> Table:
        return BootResourceSetTable

    def get_model_factory(self) -> type[BootResourceSet]:
        return BootResourceSet

    async def get_latest_for_boot_resource(
        self, boot_resource_id: int
    ) -> BootResourceSet | None:
        stmt = (
            self.select_all_statement()
            .where(eq(BootResourceSetTable.c.resource_id, boot_resource_id))
            .order_by(desc(BootResourceSetTable.c.id))
            .limit(1)
        )
        result = (await self.execute_stmt(stmt)).all()
        if result:
            return self.mapper.to_domain(result[0]._mapping)
        return None

    async def get_many_newest_to_oldest_for_boot_resource(
        self, boot_resource_id: int
    ) -> List[BootResourceSet]:
        stmt = (
            self.select_all_statement()
            .where(eq(BootResourceSetTable.c.resource_id, boot_resource_id))
            .order_by(desc(BootResourceSetTable.c.id))
        )
        result = (await self.execute_stmt(stmt)).all()
        return [self.mapper.to_domain(row._mapping) for row in result]
