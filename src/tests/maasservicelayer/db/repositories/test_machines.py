#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.node import NodeStatus
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.machines import (
    MachineClauseFactory,
    MachinesRepository,
)
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
from tests.fixtures.factories.resource_pools import create_test_resource_pool
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestMachineClauseFactory:
    def test_builder(self) -> None:
        clause = MachineClauseFactory.with_resource_pool_ids(None)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_node.pool_id IN (NULL) AND (1 != 1)")

        clause = MachineClauseFactory.with_resource_pool_ids({1, 2, 3})
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_node.pool_id IN (1, 2, 3)")
        clause = MachineClauseFactory.with_owner(None)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("auth_user.username IS NULL")
        clause = MachineClauseFactory.with_owner("test")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("auth_user.username = 'test'")


class TestMachinesRepository(RepositoryCommonTests[Machine]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> MachinesRepository:
        return MachinesRepository(Context(connection=db_connection))

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
    async def test_get_by_id_not_found(
        self, repository_instance: MachinesRepository
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_get_by_id(
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

    async def test_list_with_query(
        self, repository_instance: MachinesRepository, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        rp1 = await create_test_resource_pool(fixture, name="pool1")
        rp2 = await create_test_resource_pool(fixture, name="pool2")
        user1 = await create_test_user(fixture, username="user1")
        user2 = await create_test_user(fixture, username="user2")
        for i in range(5):
            await create_test_machine(
                fixture,
                description=str(i),
                bmc=bmc,
                user=user1,
                pool_id=rp1.id,
            )
        for i in range(5):
            await create_test_machine(
                fixture,
                description=str(i),
                bmc=bmc,
                user=user2,
                pool_id=rp2.id,
            )
        machines_repository = repository_instance
        retrieved_machines = await machines_repository.list(
            token=None,
            size=20,
            query=QuerySpec(
                where=MachineClauseFactory.with_resource_pool_ids({rp1.id})
            ),
        )
        assert len(retrieved_machines.items) == 5
        # Here we do the assert on the owner since we don't store info on pools yet.
        assert all(
            machine.owner == "user1" for machine in retrieved_machines.items
        )

        retrieved_machines = await machines_repository.list(
            token=None,
            size=20,
            query=QuerySpec(
                where=MachineClauseFactory.with_owner(user2.username)
            ),
        )

        assert len(retrieved_machines.items) == 5
        assert all(
            machine.owner == "user2" for machine in retrieved_machines.items
        )

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

    async def test_count_machines_by_statuses_no_machines(
        self, repository_instance: MachinesRepository
    ):
        result = await repository_instance.count_machines_by_statuses()
        assert all(value == 0 for value in result.__dict__.values())

    async def test_count_machines_by_statuses(
        self, repository_instance: MachinesRepository, fixture: Fixture
    ):
        machines_to_be_created_with_status = {
            NodeStatus.ALLOCATED: 1,
            NodeStatus.DEPLOYED: 2,
            NodeStatus.READY: 3,
            NodeStatus.FAILED_DEPLOYMENT: 1,
            NodeStatus.FAILED_DISK_ERASING: 1,
            NodeStatus.FAILED_ENTERING_RESCUE_MODE: 1,
            NodeStatus.FAILED_EXITING_RESCUE_MODE: 1,
            NodeStatus.FAILED_RELEASING: 2,
            NodeStatus.FAILED_TESTING: 2,
            NodeStatus.NEW: 1,
            NodeStatus.TESTING: 1,
            NodeStatus.DEPLOYING: 1,
        }
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        for status, count in machines_to_be_created_with_status.items():
            for i in range(count):
                await create_test_machine(
                    fixture, bmc=bmc, user=user, status=status
                )

        result = await repository_instance.count_machines_by_statuses()
        assert result.allocated == 1
        assert result.deployed == 2
        assert result.ready == 3
        assert result.error == 8
        assert result.other == 3
