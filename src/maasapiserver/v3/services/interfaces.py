from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.interfaces import InterfaceRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.interfaces import Interface


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
