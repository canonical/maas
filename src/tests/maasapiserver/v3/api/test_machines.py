from maasapiserver.v3.api.models.responses.machines import MachinesListResponse
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.machines import Machine
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
)


class TestMachinesApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        def _assert_machine_in_list(
            machine: Machine, machines_response: MachinesListResponse
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

        async def create_pagination_test_resources(
            fixture: Fixture, size: int
        ) -> list[Machine]:
            bmc = await create_test_bmc(fixture)
            user = await create_test_user(fixture)
            created_machines = [
                (
                    await create_test_machine(
                        fixture, description=str(i), bmc=bmc, user=user
                    )
                )
                for i in range(size)
            ]
            return created_machines

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/machines",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig[
                    MachinesListResponse
                ](
                    response_type=MachinesListResponse,
                    create_resources_routine=create_pagination_test_resources,
                    assert_routine=_assert_machine_in_list,
                ),
            ),
        ]
