#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.machines import MachinesRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.machines import Machine, PciDevice, UsbDevice
from maasservicelayer.services._base import Service


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

    async def list_machine_pci_devices(
        self, system_id: str, token: str | None, size: int
    ) -> ListResult[PciDevice]:
        return await self.machines_repository.list_machine_pci_devices(
            system_id=system_id, token=token, size=size
        )
