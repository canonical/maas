#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.workflows.msm import MachinesCountByStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.machines import MachinesRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.machines import PciDevice, UsbDevice
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.scriptresult import ScriptResultsService
from maasservicelayer.services.secrets import SecretsService


class MachinesService(NodesService):
    def __init__(
        self,
        context: Context,
        secrets_service: SecretsService,
        events_service: EventsService,
        scriptresults_service: ScriptResultsService,
        machines_repository: MachinesRepository,
    ):
        super().__init__(
            context,
            secrets_service,
            events_service,
            scriptresults_service,
            machines_repository,
        )
        self.machines_repository = machines_repository

    async def list_machine_usb_devices(
        self, system_id: str, page: int, size: int
    ) -> ListResult[UsbDevice]:
        return await self.machines_repository.list_machine_usb_devices(
            system_id=system_id, page=page, size=size
        )

    async def list_machine_pci_devices(
        self, system_id: str, page: int, size: int
    ) -> ListResult[PciDevice]:
        return await self.machines_repository.list_machine_pci_devices(
            system_id=system_id, page=page, size=size
        )

    async def count_machines_by_statuses(self) -> MachinesCountByStatus:
        return await self.machines_repository.count_machines_by_statuses()
