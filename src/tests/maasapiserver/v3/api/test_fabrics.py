# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from httpx import AsyncClient

from maasapiserver.v3.api.models.responses.fabrics import FabricsListResponse
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.fabrics import Fabric
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import ApiCommonTests, EndpointDetails


class TestFabricsApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/fabrics",
                user_role=UserRole.USER,
            )
        ]

    def _assert_fabric_in_list(
        self, fabric: Fabric, fabrics_response: FabricsListResponse
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

    # GET /fabrics
    async def test_list(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ):
        created_fabrics = []
        for i in range(10):
            created_fabrics.append(
                Fabric(
                    **(
                        await create_test_fabric_entry(
                            fixture,
                            name=str(i),
                            description=str(i),
                            class_type=str(i),
                        )
                    )
                )
            )

        next_page_link = f"{V3_API_PREFIX}/fabrics?size=2"
        last_page = 4
        for page in range(5):  # There should be 5 pages
            response = await authenticated_user_api_client_v3.get(
                next_page_link
            )
            fabrics_response = FabricsListResponse(**response.json())
            assert fabrics_response.kind == "FabricsList"
            assert len(fabrics_response.items) == 2
            self._assert_fabric_in_list(
                created_fabrics.pop(), fabrics_response
            )
            self._assert_fabric_in_list(
                created_fabrics.pop(), fabrics_response
            )
            if last_page == page:
                assert fabrics_response.next is None
            else:
                next_page_link = fabrics_response.next
