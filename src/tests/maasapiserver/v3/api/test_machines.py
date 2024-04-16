from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.models.responses.machines import MachinesListResponse
from maasapiserver.v3.constants import EXTERNAL_V3_API_PREFIX
from maasapiserver.v3.models.machines import Machine
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    ApiEndpointsRoles,
    EndpointDetails,
)


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestMachinesApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> ApiEndpointsRoles:
        return ApiEndpointsRoles(
            unauthenticated_endpoints=[],
            user_endpoints=[
                EndpointDetails(
                    method="GET",
                    path="/api/v3/machines",
                ),
            ],
            admin_endpoints=[],
        )

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
            machine.to_response(f"{EXTERNAL_V3_API_PREFIX}/machines")
            == machine_response
        )

    @pytest.mark.parametrize("machines_size", range(0, 10))
    async def test_list_parameters_200(
        self,
        authenticated_user_api_client_v3: AsyncClient,
        fixture: Fixture,
        machines_size: int,
    ) -> None:
        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        created_machines = [
            (
                await create_test_machine(
                    fixture, description=str(i), bmc=bmc, user=user
                )
            )
            for i in range(0, machines_size)
        ]

        response = await authenticated_user_api_client_v3.get(
            "/api/v3/machines"
        )
        assert response.status_code == 200

        machines_response = MachinesListResponse(**response.json())
        assert machines_response.kind == "MachinesList"
        assert machines_response.total == machines_size
        assert len(machines_response.items) == machines_size
        for machine in created_machines:
            self._assert_machine_in_list(machine, machines_response)

        for page in range(1, machines_size // 2):
            response = await authenticated_user_api_client_v3.get(
                f"/api/v3/machines?page={page}&size=2"
            )
            assert response.status_code == 200
            machines_response = MachinesListResponse(**response.json())
            assert machines_response.kind == "MachinesList"
            assert machines_response.total == machines_size
            assert (
                len(machines_response.items) == 2
                if page != machines_size // 2
                else (machines_size % 2 or 2)
            )

    @pytest.mark.parametrize(
        "page,size", [(1, 0), (0, 1), (-1, -1), (1, 1001)]
    )
    async def test_list_422(
        self,
        page: int,
        size: int,
        authenticated_user_api_client_v3: AsyncClient,
    ) -> None:
        response = await authenticated_user_api_client_v3.get(
            f"/api/v3/machines?page={page}&size={size}"
        )
        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
