from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.machines import MachinesRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.machines import Machine, UsbDevice


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
        return await self.machines_repository.list(token=token, size=size)

    async def list_machine_usb_devices(
        self, system_id: str, token: str | None, size: int
    ) -> ListResult[UsbDevice]:
        return await self.machines_repository.list_machine_usb_devices(
            system_id=system_id, token=token, size=size
        )
