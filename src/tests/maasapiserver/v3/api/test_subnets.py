# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from httpx import AsyncClient

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.models.responses.subnets import SubnetsListResponse
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.subnets import Subnet
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
)


class TestSubnetApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        def _assert_subnet_in_list(
            subnet: Subnet, subnets_response: SubnetsListResponse
        ):
            subnet_response = next(
                filter(
                    lambda resp: resp.id == subnet.id, subnets_response.items
                )
            )
            assert subnet.id == subnet_response.id
            assert subnet.name == subnet_response.name
            assert subnet.description == subnet_response.description
            assert subnet.cidr == subnet_response.cidr
            assert subnet.dns_servers == subnet_response.dns_servers
            assert subnet.gateway_ip == subnet_response.gateway_ip
            assert subnet.rdns_mode == subnet_response.rdns_mode
            assert subnet.allow_proxy == subnet_response.allow_proxy
            assert subnet.active_discovery == subnet_response.active_discovery
            assert subnet.managed == subnet_response.managed
            assert subnet.allow_dns == subnet_response.allow_dns
            assert (
                subnet.disabled_boot_architectures
                == subnet_response.disabled_boot_architectures
            )

        async def create_pagination_test_resources(
            fixture: Fixture, size: int
        ) -> list[Subnet]:
            created_subnets = [
                Subnet(
                    **await create_test_subnet_entry(
                        fixture, name=str(i), description=str(i)
                    )
                )
                for i in range(size)
            ]
            return created_subnets

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/subnets",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig[
                    SubnetsListResponse
                ](
                    response_type=SubnetsListResponse,
                    create_resources_routine=create_pagination_test_resources,
                    assert_routine=_assert_subnet_in_list,
                ),
            ),
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/subnets/1",
                user_role=UserRole.USER,
            ),
        ]

    # GET /subnets/{subnet_id}
    async def test_get_200(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        created_subnet = Subnet(
            **(
                await create_test_subnet_entry(
                    fixture, name="subnet", description="descr"
                )
            )
        )
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/subnets/{created_subnet.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "Subnet",
            "id": created_subnet.id,
            "name": created_subnet.name,
            "description": created_subnet.description,
            "cidr": str(created_subnet.cidr),
            "dns_servers": created_subnet.dns_servers,
            "gateway_ip": created_subnet.gateway_ip,
            "rdns_mode": created_subnet.rdns_mode,
            "allow_proxy": created_subnet.allow_proxy,
            "active_discovery": created_subnet.active_discovery,
            "managed": created_subnet.managed,
            "allow_dns": created_subnet.allow_dns,
            "disabled_boot_architectures": created_subnet.disabled_boot_architectures,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "vlan": {
                "href": f"{V3_API_PREFIX}/vlans?filter=subnet_id eq {created_subnet.id}"
            },
            "_links": {
                "self": {
                    "href": f"{V3_API_PREFIX}/subnets/{created_subnet.id}"
                }
            },
        }

    async def test_get_404(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/subnets/100"
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
            f"{V3_API_PREFIX}/subnets/xyz"
        )
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
