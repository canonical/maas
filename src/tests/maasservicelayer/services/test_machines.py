# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.node import NodeStatus
from maascommon.enums.power import PowerState
from maascommon.workflows.msm import MachinesCountByStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.machines import MachinesRepository
from maasservicelayer.models.base import ListResult, MaasBaseModel
from maasservicelayer.models.machines import Machine, PciDevice, UsbDevice
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.machines import MachinesService
from maasservicelayer.services.scriptresult import ScriptResultsService
from maasservicelayer.services.secrets import SecretsService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonMachinesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return MachinesService(
            context=Context(connection=Mock(AsyncConnection)),
            secrets_service=Mock(SecretsService),
            machines_repository=Mock(MachinesRepository),
            events_service=Mock(EventsService),
            scriptresults_service=Mock(ScriptResultsService),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return Machine(
            id=2,
            description="test_description_2",
            created=utcnow(),
            updated=utcnow(),
            system_id="e8slyu",
            owner="admin",
            cpu_speed=1800,
            memory=16384,
            osystem="ubuntu",
            architecture="amd64/generic",
            distro_series="jammy",
            hwe_kernel=None,
            locked=False,
            cpu_count=8,
            status=NodeStatus.NEW,
            power_type=None,
            fqdn="maas.local",
            hostname="hostname",
            power_state=PowerState.ON,
        )


@pytest.mark.asyncio
class TestMachinesService:
    async def test_list_machine_usb_devices(self) -> None:
        machines_repository_mock = Mock(MachinesRepository)
        machines_repository_mock.list_machine_usb_devices.return_value = (
            ListResult[UsbDevice](items=[], total=0)
        )
        machines_service = MachinesService(
            context=Context(connection=Mock(AsyncConnection)),
            secrets_service=Mock(SecretsService),
            machines_repository=machines_repository_mock,
            events_service=Mock(EventsService),
            scriptresults_service=Mock(ScriptResultsService),
        )
        usb_devices_list = await machines_service.list_machine_usb_devices(
            system_id="dummy", page=1, size=1
        )
        machines_repository_mock.list_machine_usb_devices.assert_called_once_with(
            system_id="dummy", page=1, size=1
        )
        assert usb_devices_list.total == 0
        assert usb_devices_list.items == []

    async def test_list_machine_pci_devices(self) -> None:
        machines_repository_mock = Mock(MachinesRepository)
        machines_repository_mock.list_machine_pci_devices.return_value = (
            ListResult[PciDevice](items=[], total=0)
        )
        machines_service = MachinesService(
            context=Context(connection=Mock(AsyncConnection)),
            secrets_service=Mock(SecretsService),
            machines_repository=machines_repository_mock,
            events_service=Mock(EventsService),
            scriptresults_service=Mock(ScriptResultsService),
        )
        pci_devices_list = await machines_service.list_machine_pci_devices(
            system_id="dummy", page=1, size=1
        )
        machines_repository_mock.list_machine_pci_devices.assert_called_once_with(
            system_id="dummy", page=1, size=1
        )
        assert pci_devices_list.total == 0
        assert pci_devices_list.items == []

    async def test_count_machines_by_statuses(self) -> None:
        machines_repository_mock = Mock(MachinesRepository)
        return_value = Mock(MachinesCountByStatus)
        machines_repository_mock.count_machines_by_statuses.return_value = (
            return_value
        )
        machines_service = MachinesService(
            context=Context(connection=Mock(AsyncConnection)),
            secrets_service=Mock(SecretsService),
            machines_repository=machines_repository_mock,
            events_service=Mock(EventsService),
            scriptresults_service=Mock(ScriptResultsService),
        )
        result = await machines_service.count_machines_by_statuses()
        assert result is return_value
        machines_repository_mock.count_machines_by_statuses.assert_called_once()
