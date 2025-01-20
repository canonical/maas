#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Type

from sqlalchemy import select, Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ResourcePoolTable
from maasservicelayer.models.resource_pools import ResourcePool


class ResourcePoolClauseFactory(ClauseFactory):
    @classmethod
    def with_ids(cls, ids: Optional[list[int]]) -> Clause:
        return Clause(condition=ResourcePoolTable.c.id.in_(ids))


class ResourcePoolRepository(BaseRepository[ResourcePool]):
    def get_repository_table(self) -> Table:
        return ResourcePoolTable

    def get_model_factory(self) -> Type[ResourcePool]:
        return ResourcePool

    async def list_ids(self) -> set[int]:
        stmt = select(ResourcePoolTable.c.id).select_from(ResourcePoolTable)
        result = (await self.connection.execute(stmt)).all()
        return {row.id for row in result}
