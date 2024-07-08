# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.fabrics import FabricsRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.fabrics import Fabric


class FabricsService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        fabrics_repository: FabricsRepository | None = None,
    ):
        super().__init__(connection)
        self.fabrics_repository = (
            fabrics_repository
            if fabrics_repository
            else FabricsRepository(connection)
        )

    async def list(self, token: str | None, size: int) -> ListResult[Fabric]:
        return await self.fabrics_repository.list(token=token, size=size)

    async def get_by_id(self, id: int) -> Fabric | None:
        return await self.fabrics_repository.find_by_id(id=id)
