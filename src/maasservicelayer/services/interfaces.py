#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.services._base import Service


class InterfacesService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        interface_repository: InterfaceRepository | None = None,
    ):
        super().__init__(connection)
        self.interface_repository = (
            interface_repository
            if interface_repository
            else InterfaceRepository(connection)
        )

    async def list(
        self, node_id: int, token: str | None, size: int
    ) -> ListResult[Interface]:
        return await self.interface_repository.list(
            node_id=node_id, token=token, size=size
        )
