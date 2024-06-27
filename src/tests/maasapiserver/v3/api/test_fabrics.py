# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.models.responses.fabrics import FabricsListResponse
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.fabrics import Fabric
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
)


class TestFabricsApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        def _assert_fabric_in_list(
            fabric: Fabric, fabrics_response: FabricsListResponse
        ) -> None:
            fabric_response = next(
                filter(
                    lambda fabric_response: fabric.id == fabric_response.id,
                    fabrics_response.items,
                )
            )
            assert fabric.id == fabric_response.id
            assert fabric.name == fabric_response.name
            assert fabric.description == fabric_response.description
            assert fabric.class_type == fabric_response.class_type
            assert fabric_response.vlans.href.endswith(
                f"/vlans?filter=fabric_id eq {fabric.id}"
            )

        async def create_pagination_test_resources(
            fixture: Fixture, size: int
        ) -> list[Fabric]:
            created_fabrics = []
            for i in range(size):
                created_fabrics.append(
                    await create_test_fabric_entry(
                        fixture,
                        name=str(i),
                        description=str(i),
                        class_type=str(i),
                    )
                )
            return created_fabrics

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/fabrics",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig[
                    FabricsListResponse
                ](
                    response_type=FabricsListResponse,
                    create_resources_routine=create_pagination_test_resources,
                    assert_routine=_assert_fabric_in_list,
                ),
            )
        ]
