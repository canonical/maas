from math import ceil

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.db.machines import MachinesRepository
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestMachinesRepository:
    @pytest.mark.parametrize("page_size", range(1, 12))
    async def test_list(
        self, page_size: int, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)

        machine_count = 10
        machines_repository = MachinesRepository(db_connection)
        created_machines = [
            (
                await create_test_machine(
                    fixture, description=str(i), bmc=bmc, user=user
                )
            )
            for i in range(0, machine_count)
        ][::-1]
        total_pages = ceil(machine_count / page_size)
        for page in range(1, total_pages + 1):
            machines_result = await machines_repository.list(
                PaginationParams(size=page_size, page=page)
            )
            assert machines_result.total == machine_count
            assert total_pages == ceil(machines_result.total / page_size)
            if page == total_pages:  # last page may have fewer elements
                assert len(machines_result.items) == (
                    page_size
                    - ((total_pages * page_size) % machines_result.total)
                )
            else:
                assert len(machines_result.items) == page_size
            for machine in created_machines[
                ((page - 1) * page_size) : ((page * page_size))
            ]:
                assert machine in machines_result.items

    async def test_list_only_machines_nodes_are_returned(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)

        await create_test_region_controller_entry(fixture)
        machines_repository = MachinesRepository(db_connection)
        await create_test_machine(
            fixture, description="machine", bmc=bmc, user=user
        )

        machines_result = await machines_repository.list(
            PaginationParams(size=10, page=1)
        )
        assert machines_result.total == 1
        assert len(machines_result.items) == 1
