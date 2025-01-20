#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import select, Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import DefaultResourceTable, ZoneTable
from maasservicelayer.models.zones import Zone


class ZonesClauseFactory(ClauseFactory):
    @classmethod
    def with_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=ZoneTable.c.id.in_(ids))


class ZonesRepository(BaseRepository[Zone]):
    def get_repository_table(self) -> Table:
        return ZoneTable

    def get_model_factory(self) -> Type[Zone]:
        return Zone

    async def get_default_zone(self) -> Zone:
        stmt = (
            select(ZoneTable)
            .select_from(ZoneTable)
            .join(
                DefaultResourceTable,
                eq(DefaultResourceTable.c.zone_id, ZoneTable.c.id),
            )
        )
        result = await self.connection.execute(stmt)
        # By design the default zone is always present.
        zone = result.first()
        return Zone(**zone._asdict())
