# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.reservedips import ReservedIPsRepository
from maasservicelayer.models.reservedips import ReservedIP
from maasservicelayer.services._base import Service


class ReservedIPsService(Service):
    def __init__(
        self, context: Context, reservedips_repository: ReservedIPsRepository
    ):
        super().__init__(context)
        self.reservedips_repository = reservedips_repository

    async def delete(self, query: QuerySpec) -> ReservedIP | None:
        return await self.reservedips_repository.delete(query)
