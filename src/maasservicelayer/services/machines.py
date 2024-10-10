#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.machines import MachinesRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.machines import (
    Machine,
    MachinesCountByStatus,
    PciDevice,
    UsbDevice,
)
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.secrets import SecretsService


class MachinesService(NodesService):
    def __init__(
        self,
        connection: AsyncConnection,
        secrets_service: SecretsService,
        machines_repository: MachinesRepository | None = None,
    ):
        super().__init__(connection, secrets_service)
        self.machines_repository = (
            machines_repository
            if machines_repository
            else MachinesRepository(connection)
        )

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[Machine]:
        return await self.machines_repository.list(
            token=token, size=size, query=query
        )

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

    async def count_machines_by_statuses(self) -> MachinesCountByStatus:
        return await self.machines_repository.count_machines_by_statuses()
