from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.models.responses.interfaces import (
    InterfaceListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.interfaces import Interface
from tests.fixtures.factories.bmc import create_test_bmc
from tests.fixtures.factories.interface import create_test_interface
from tests.fixtures.factories.machines import create_test_machine
from tests.fixtures.factories.node_config import create_test_node_config_entry
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestInterfaceApi:
    @pytest.mark.parametrize("size", range(1, 10))
    async def test_get_lists_resources(
        self,
        fixture: Fixture,
        authenticated_user_api_client_v3: AsyncClient,
        size: int,
    ) -> None:
        def _assert_interface_in_list(
            interface: Interface, interfaces_response: InterfaceListResponse
        ) -> None:
            interface_response = next(
                filter(
                    lambda interface_response: interface.id
                    == interface_response.id,
                    interfaces_response.items,
                )
            )
            assert interface.id == interface_response.id

            # We have no way of knowing the node id to construct the path
            iface = interface.to_response(
                str(interface_response.hal_links.self.href).rsplit("/", 1)[0]
            )
            assert (
                iface == interface_response
            ), f"{iface} does not match {interface_response}!"

        bmc = await create_test_bmc(fixture)
        user = await create_test_user(fixture)
        machine = (
            await create_test_machine(fixture, bmc=bmc, user=user)
        ).dict()
        config = await create_test_node_config_entry(fixture, node=machine)
        machine["current_config_id"] = config["id"]

        created_interfaces = [
            (
                await create_test_interface(
                    fixture,
                    description=str(i),
                    node=machine,
                    ip_count=4,
                )
            )
            for i in range(0, size)
        ]

        path = f"{V3_API_PREFIX}/machines/{machine['id']}/interfaces"
        response = await authenticated_user_api_client_v3.get(path)
        assert response.status_code == 200

        interfaces = InterfaceListResponse(**response.json())
        assert interfaces.total == size
        assert len(interfaces.items) == size

        for resource in created_interfaces:
            _assert_interface_in_list(resource, interfaces)

        for page in range(1, size // 2):
            response = await authenticated_user_api_client_v3.get(
                f"{path}?page={page}&size=2",
            )
            assert response.status_code == 200
            interfaces = InterfaceListResponse(**response.json())
            assert interfaces.total == size
            assert (
                len(interfaces.items) == 2
                if page != size // 2
                else (size % 2 or 2)
            )
