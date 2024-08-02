# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from httpx import AsyncClient

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
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
                    Fabric, FabricsListResponse
                ](
                    response_type=FabricsListResponse,
                    create_resources_routine=create_pagination_test_resources,
                ),
            ),
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/fabrics/1",
                user_role=UserRole.USER,
            ),
        ]

    # GET /fabric/{ID}
    async def test_get_200(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        created_fabric = await create_test_fabric_entry(fixture)
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/fabrics/{created_fabric.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "Fabric",
            "id": created_fabric.id,
            "name": created_fabric.name,
            "description": created_fabric.description,
            "class_type": created_fabric.class_type,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "vlans": {
                "href": f"{V3_API_PREFIX}/vlans?filter=fabric_id eq {created_fabric.id}"
            },
            "_links": {
                "self": {
                    "href": f"{V3_API_PREFIX}/fabrics/{created_fabric.id}"
                }
            },
        }

    async def test_get_404(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/fabrics/100"
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
            f"{V3_API_PREFIX}/fabrics/xyz"
        )
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
