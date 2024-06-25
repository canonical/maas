from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.machines import MachinesRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.machines import Machine


class MachinesService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        machines_repository: MachinesRepository | None = None,
    ):
        super().__init__(connection)
        self.machines_repository = (
            machines_repository
            if machines_repository
            else MachinesRepository(connection)
        )

    async def list(self, token: str | None, size: int) -> ListResult[Machine]:
        return await self.machines_repository.list_with_token(
            token=token, size=size
        )
