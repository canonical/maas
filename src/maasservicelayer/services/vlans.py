# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from typing import List

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.vlans import VlansRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services._base import Service


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

    async def get_by_id(self, id: int) -> Vlan | None:
        return await self.vlans_repository.find_by_id(id=id)

    async def get_node_vlans(self, query: QuerySpec) -> List[Vlan]:
        return await self.vlans_repository.get_node_vlans(query=query)
