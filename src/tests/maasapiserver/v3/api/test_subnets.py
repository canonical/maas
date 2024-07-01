# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

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
            )
        ]
