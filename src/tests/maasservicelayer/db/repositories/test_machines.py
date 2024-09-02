#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.machines import MachinesRepository
from maasservicelayer.models.machines import Machine
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.fixtures.factories.node_config import (
    create_test_node_config_entry,
    create_test_numa_node,
    create_test_pci_device,
    create_test_usb_device,
)
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestMachinesRepository(RepositoryCommonTests[Machine]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> MachinesRepository:
        return MachinesRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Machine]:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)

        created_machines = [
            (
                await create_test_machine(
                    fixture, description=str(i), bmc=bmc, user=user
                )
            )
            for i in range(num_objects)
        ]
        return created_machines

    @pytest.fixture
    async def _created_instance(self, fixture: Fixture) -> Machine:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)

        return await create_test_machine(
            fixture, description="description", bmc=bmc, user=user
        )

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_find_by_id_not_found(
        self, repository_instance: MachinesRepository
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_find_by_id(
        self,
        repository_instance: MachinesRepository,
        _created_instance: Machine,
    ):
        pass

    async def test_list_only_machines_nodes_are_returned(
        self, repository_instance: MachinesRepository, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)

        await create_test_region_controller_entry(fixture)
        machines_repository = repository_instance
        await create_test_machine(
            fixture, description="machine", bmc=bmc, user=user
        )

        machines_result = await machines_repository.list(token=None, size=10)
        assert machines_result.next_token is None
        assert len(machines_result.items) == 1

    async def test_list_machine_usb_devices(
        self, repository_instance: MachinesRepository, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = (
            await create_test_machine(fixture, bmc=bmc, user=user)
        ).dict()
        config = await create_test_node_config_entry(fixture, node=machine)
        numa_node = await create_test_numa_node(fixture, node=machine)
        devices = [
            (
                await create_test_usb_device(
                    fixture,
                    numa_node=numa_node,
                    config=config,
                    vendor_name=str(i),
                )
            )
            for i in range(3)
        ]

        machines_repository = repository_instance
        devices_result = await machines_repository.list_machine_usb_devices(
            system_id=machine["system_id"], token=None, size=2
        )
        assert devices_result.next_token is not None
        assert len(devices_result.items) == 2
        assert devices.pop() in devices_result.items
        assert devices.pop() in devices_result.items

        devices_result = await machines_repository.list_machine_usb_devices(
            system_id=machine["system_id"],
            token=devices_result.next_token,
            size=2,
        )
        assert devices_result.next_token is None
        assert len(devices_result.items) == 1
        assert devices_result.items[0] == devices.pop()

    async def test_list_machine_pci_devices(
        self, repository_instance: MachinesRepository, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = (
            await create_test_machine(fixture, bmc=bmc, user=user)
        ).dict()
        config = await create_test_node_config_entry(fixture, node=machine)
        numa_node = await create_test_numa_node(fixture, node=machine)
        devices = [
            (
                await create_test_pci_device(
                    fixture,
                    numa_node=numa_node,
                    config=config,
                    pci_address=f"0000:00:00.{i}",
                )
            )
            for i in range(3)
        ]

        machines_repository = repository_instance
        devices_result = await machines_repository.list_machine_pci_devices(
            system_id=machine["system_id"], token=None, size=2
        )
        assert devices_result.next_token is not None
        assert len(devices_result.items) == 2
        assert devices.pop() in devices_result.items
        assert devices.pop() in devices_result.items

        devices_result = await machines_repository.list_machine_pci_devices(
            system_id=machine["system_id"],
            token=devices_result.next_token,
            size=2,
        )
        assert devices_result.next_token is None
        assert len(devices_result.items) == 1
        assert devices_result.items[0] == devices.pop()
