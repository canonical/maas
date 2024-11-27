# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.spaces import SpacesRepository
from maasservicelayer.db.repositories.vlans import (
    VlanResourceBuilder,
    VlansClauseFactory,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.spaces import Space
from maasservicelayer.services._base import Service
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow


class SpacesService(Service):
    def __init__(
        self,
        context: Context,
        vlans_service: VlansService,
        spaces_repository: SpacesRepository,
    ):
        super().__init__(context)
        self.vlans_service = vlans_service
        self.spaces_repository = spaces_repository

    async def list(self, token: str | None, size: int) -> ListResult[Space]:
        return await self.spaces_repository.list(token=token, size=size)

    async def get_by_id(self, id: int) -> Space | None:
        return await self.spaces_repository.get_by_id(id=id)

    async def create(self, resource: CreateOrUpdateResource) -> Space:
        return await self.spaces_repository.create(resource=resource)

    async def delete_by_id(
        self, id: int, etag_if_match: str | None = None
    ) -> None:
        space = await self.get_by_id(id)
        if not space:
            return None

        self.etag_check(space, etag_if_match)

        await self.spaces_repository.delete_by_id(id=id)

        # Remove this space's id from all related VLANs
        now = utcnow()
        await self.vlans_service.update(
            query=QuerySpec(where=VlansClauseFactory.with_space_id(id)),
            resource=(
                VlanResourceBuilder()
                .with_space_id(None)
                .with_updated(now)
                .build()
            ),
        )
