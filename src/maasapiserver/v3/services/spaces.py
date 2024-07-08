# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.spaces import SpacesRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.spaces import Space


class SpacesService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        spaces_repository: SpacesRepository | None = None,
    ):
        super().__init__(connection)
        self.spaces_repository = (
            spaces_repository
            if spaces_repository
            else SpacesRepository(connection)
        )

    async def list(self, token: str | None, size: int) -> ListResult[Space]:
        return await self.spaces_repository.list(token=token, size=size)

    async def get_by_id(self, id: int) -> Space | None:
        return await self.spaces_repository.find_by_id(id=id)
