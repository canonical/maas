import pytest

from maasapiserver.v3.api.models.responses.interfaces import (
    InterfaceListResponse,
)
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.interfaces import Interface
from maasapiserver.v3.models.machines import Machine
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.interface import create_test_interface
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
)


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestInterfaceApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        async def create_machine(fixture: Fixture) -> Machine:
            bmc = await create_test_bmc(fixture)
            user = await create_test_user(fixture)
            machine = await create_test_machine(fixture, bmc=bmc, user=user)
            return machine

        async def create_interface_pagination_test_resources(
            fixture: Fixture, size: int, machine: Machine
        ) -> list[Interface]:
            m = machine.dict()
            config = await create_test_node_config_entry(fixture, node=m)
            m["current_config_id"] = config["id"]

            created_interfaces = [
                (
                    await create_test_interface(
                        fixture,
                        description=str(i),
                        node=m,
                        ip_count=4,
                    )
                )
                for i in range(size)
            ]
            return created_interfaces

        return [
            EndpointDetails(
                method="GET",
                path=V3_API_PREFIX + "/machines/{0.id}/interfaces",
                user_role=UserRole.USER,
                objects_factories=[create_machine],
                pagination_config=PaginatedEndpointTestConfig[
                    Interface, InterfaceListResponse
                ](
                    response_type=InterfaceListResponse,
                    create_resources_routine=create_interface_pagination_test_resources,
                    size_parameters=range(1, 10),
                ),
            ),
        ]
