from httpx import AsyncClient

from maasapiserver.v3.api.models.responses.machines import MachinesListResponse
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.machines import Machine
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import ApiCommonTests, EndpointDetails


class TestMachinesApi(ApiCommonTests):
    def _assert_machine_in_list(
        self, machine: Machine, machines_response: MachinesListResponse
    ) -> None:
        machine_response = next(
            filter(
                lambda machine_response: machine.id == machine_response.id,
                machines_response.items,
            )
        )
        assert machine.id == machine_response.id
        assert (
            machine.to_response(f"{V3_API_PREFIX}/machines")
            == machine_response
        )

    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/machines",
                user_role=UserRole.USER,
            ),
        ]

    # GET /machines
    async def test_list(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ):
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        created_machines = [
            (
                await create_test_machine(
                    fixture, description=str(i), bmc=bmc, user=user
                )
            )
            for i in range(0, 10)
        ]

        next_page_link = f"{V3_API_PREFIX}/machines?size=2"
        for page in range(5):  # There should be 5 pages
            response = await authenticated_user_api_client_v3.get(
                next_page_link
            )
            machines_response = MachinesListResponse(**response.json())
            assert machines_response.kind == "MachinesList"
            assert len(machines_response.items) == 2
            self._assert_machine_in_list(
                created_machines.pop(), machines_response
            )
            self._assert_machine_in_list(
                created_machines.pop(), machines_response
            )
            next_page_link = machines_response.next
        # There was no next page
        assert next_page_link is None
