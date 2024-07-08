import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.machines import MachinesRepository
from maasapiserver.v3.models.machines import Machine
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.db.base import RepositoryCommonTests


class TestMachinesRepository(RepositoryCommonTests[Machine]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> MachinesRepository:
        return MachinesRepository(db_connection)

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture
    ) -> tuple[list[Machine], int]:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)

        machine_count = 10
        created_machines = [
            (
                await create_test_machine(
                    fixture, description=str(i), bmc=bmc, user=user
                )
            )
            for i in range(machine_count)
        ][::-1]
        return created_machines, machine_count

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
