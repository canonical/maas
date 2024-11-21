# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.fabrics import FabricsRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.fabrics import Fabric
from maasservicelayer.services._base import Service


class FabricsService(Service):
    def __init__(
        self,
        context: Context,
        fabrics_repository: FabricsRepository | None = None,
    ):
        super().__init__(context)
        self.fabrics_repository = (
            fabrics_repository
            if fabrics_repository
            else FabricsRepository(context)
        )

    async def list(self, token: str | None, size: int) -> ListResult[Fabric]:
        return await self.fabrics_repository.list(token=token, size=size)

    async def get_by_id(self, id: int) -> Fabric | None:
        return await self.fabrics_repository.get_by_id(id=id)
