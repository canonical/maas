# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.spaces import SpacesRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.spaces import Space
from maasservicelayer.services._base import Service


class SpacesService(Service):
    def __init__(
        self,
        context: Context,
        spaces_repository: SpacesRepository | None = None,
    ):
        super().__init__(context)
        self.spaces_repository = (
            spaces_repository
            if spaces_repository
            else SpacesRepository(context)
        )

    async def list(self, token: str | None, size: int) -> ListResult[Space]:
        return await self.spaces_repository.list(token=token, size=size)

    async def get_by_id(self, id: int) -> Space | None:
        return await self.spaces_repository.get_by_id(id=id)
