# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.staticroutes import (
    StaticRoutesRepository,
)
from maasservicelayer.models.staticroutes import StaticRoute
from maasservicelayer.services._base import Service


class StaticRoutesService(Service):
    def __init__(
        self, context: Context, staticroutes_repository: StaticRoutesRepository
    ):
        super().__init__(context)
        self.staticroutes_repository = staticroutes_repository

    async def delete(self, query: QuerySpec) -> StaticRoute | None:
        return await self.staticroutes_repository.delete(query)
