# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.machines import MachinesRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.machines import Machine, PciDevice, UsbDevice
from maasapiserver.v3.services.machines import MachinesService


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestMachinesService:
    async def test_list(self, db_connection: AsyncConnection) -> None:
        machines_repository_mock = Mock(MachinesRepository)
        machines_repository_mock.list = AsyncMock(
            return_value=ListResult[Machine](items=[], next_token=None)
        )
        machines_service = MachinesService(
            connection=db_connection,
            machines_repository=machines_repository_mock,
        )
        machines_list = await machines_service.list(token=None, size=1)
        machines_repository_mock.list.assert_called_once_with(
            token=None, size=1
        )
        assert machines_list.next_token is None
        assert machines_list.items == []

    async def test_list_machine_usb_devices(
        self, db_connection: AsyncConnection
    ) -> None:
        machines_repository_mock = Mock(MachinesRepository)
        machines_repository_mock.list_machine_usb_devices = AsyncMock(
            return_value=ListResult[UsbDevice](items=[], next_token=None)
        )
        machines_service = MachinesService(
            connection=db_connection,
            machines_repository=machines_repository_mock,
        )
        usb_devices_list = await machines_service.list_machine_usb_devices(
            system_id="dummy", token=None, size=1
        )
        machines_repository_mock.list_machine_usb_devices.assert_called_once_with(
            system_id="dummy", token=None, size=1
        )
        assert usb_devices_list.next_token is None
        assert usb_devices_list.items == []

    async def test_list_machine_pci_devices(
        self, db_connection: AsyncConnection
    ) -> None:
        machines_repository_mock = Mock(MachinesRepository)
        machines_repository_mock.list_machine_pci_devices = AsyncMock(
            return_value=ListResult[PciDevice](items=[], next_token=None)
        )
        machines_service = MachinesService(
            connection=db_connection,
            machines_repository=machines_repository_mock,
        )
        pci_devices_list = await machines_service.list_machine_pci_devices(
            system_id="dummy", token=None, size=1
        )
        machines_repository_mock.list_machine_pci_devices.assert_called_once_with(
            system_id="dummy", token=None, size=1
        )
        assert pci_devices_list.next_token is None
        assert pci_devices_list.items == []
