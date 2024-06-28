# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

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
        def _assert_vlan_in_list(
            vlan: Vlan, vlans_response: VlansListResponse
        ):
            vlan_response = next(
                filter(lambda resp: resp.id == vlan.id, vlans_response.items)
            )
            assert vlan.id == vlan_response.id
            assert vlan.vid == vlan_response.vid
            assert vlan.name == vlan_response.name
            assert vlan.description == vlan_response.description
            assert vlan.mtu == vlan_response.mtu
            assert vlan.dhcp_on == vlan_response.dhcp_on
            assert vlan.external_dhcp == vlan_response.external_dhcp
            assert vlan.primary_rack_id == vlan_response.primary_rack
            assert vlan.secondary_rack_id == vlan_response.secondary_rack
            assert vlan.relay_vlan == vlan_response.relay_vlan
            assert vlan_response.fabric.href.endswith(
                f"fabrics/{vlan.fabric_id}"
            )
            assert vlan_response.space.href.endswith(f"spaces/{vlan.space_id}")

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
                    VlansListResponse
                ](
                    response_type=VlansListResponse,
                    create_resources_routine=create_pagination_test_resources,
                    assert_routine=_assert_vlan_in_list,
                ),
            )
        ]
