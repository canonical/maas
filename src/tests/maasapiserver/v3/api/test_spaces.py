# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from httpx import AsyncClient

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.models.responses.spaces import SpacesListResponse
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.spaces import Space
from tests.fixtures.factories.spaces import create_test_space_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
)


class TestSpaceApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        async def create_pagination_test_resources(
            fixture: Fixture, size: int
        ) -> list[Space]:
            created_spaces = [
                await create_test_space_entry(
                    fixture, name=str(i), description=str(i)
                )
                for i in range(size)
            ]
            return created_spaces

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/spaces",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig[
                    Space, SpacesListResponse
                ](
                    response_type=SpacesListResponse,
                    create_resources_routine=create_pagination_test_resources,
                ),
            ),
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/spaces/1",
                user_role=UserRole.USER,
            ),
        ]

    # GET /spaces/{space_id}
    async def test_get_200(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        created_space = await create_test_space_entry(
            fixture, name="space", description="descr"
        )
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/spaces/{created_space.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "Space",
            "id": created_space.id,
            "name": created_space.name,
            "description": created_space.description,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "vlans": {
                "href": f"{V3_API_PREFIX}/vlans?filter=space_id eq {created_space.id}"
            },
            "subnets": {
                "href": f"{V3_API_PREFIX}/subnets?filter=space_id eq {created_space.id}"
            },
            "_links": {
                "self": {"href": f"{V3_API_PREFIX}/spaces/{created_space.id}"}
            },
        }

    async def test_get_404(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/spaces/100"
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
            f"{V3_API_PREFIX}/spaces/xyz"
        )
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
