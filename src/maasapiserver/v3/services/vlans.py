# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.vlans import VlansRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.vlans import Vlan


class VlansService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        vlans_repository: VlansRepository | None = None,
    ):
        super().__init__(connection)
        self.vlans_repository = (
            vlans_repository
            if vlans_repository
            else VlansRepository(connection)
        )

    async def list(self, token: str | None, size: int) -> ListResult[Vlan]:
        return await self.vlans_repository.list(token=token, size=size)
