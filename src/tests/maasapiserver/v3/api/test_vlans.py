# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from httpx import AsyncClient

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.models.responses.vlans import VlansListResponse
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.vlans import Vlan
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
)


class TestVlanApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:

        async def create_pagination_test_resources(
            fixture: Fixture, size: int
        ) -> list[Vlan]:
            fabric = await create_test_fabric_entry(fixture)
            created_vlans = [
                Vlan(
                    **(
                        await create_test_vlan_entry(
                            fixture, fabric_id=fabric.id
                        )
                    )
                )
                for i in range(size)
            ]
            return created_vlans

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/vlans",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig[
                    Vlan, VlansListResponse
                ](
                    response_type=VlansListResponse,
                    create_resources_routine=create_pagination_test_resources,
                ),
            ),
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/vlans/1",
                user_role=UserRole.USER,
            ),
        ]

    # GET /vlans/{vlan_id}
    async def test_get_200(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        fabric = await create_test_fabric_entry(fixture)
        created_vlan = Vlan(
            **(await create_test_vlan_entry(fixture, fabric_id=fabric.id))
        )
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/vlans/{created_vlan.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "Vlan",
            "id": created_vlan.id,
            "vid": created_vlan.vid,
            "name": created_vlan.name,
            "description": created_vlan.description,
            "mtu": created_vlan.mtu,
            "dhcp_on": created_vlan.dhcp_on,
            "external_dhcp": created_vlan.external_dhcp,
            "primary_rack": created_vlan.primary_rack_id,
            "secondary_rack": created_vlan.secondary_rack_id,
            "relay_vlan": created_vlan.relay_vlan,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "fabric": {
                "href": f"{V3_API_PREFIX}/fabrics/{created_vlan.fabric_id}"
            },
            "space": None,
            "_links": {
                "self": {"href": f"{V3_API_PREFIX}/vlans/{created_vlan.id}"}
            },
        }

    async def test_get_404(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/vlans/100"
        )
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_get_422(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/vlans/xyz"
        )
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
