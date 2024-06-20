from datetime import timezone

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.models.requests.resource_pools import (
    ResourcePoolPatchRequest,
    ResourcePoolRequest,
)
from maasapiserver.v3.api.models.responses.resource_pools import (
    ResourcePoolResponse,
    ResourcePoolsListResponse,
)
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.resource_pools import ResourcePool
from tests.fixtures.factories.resource_pools import (
    create_n_test_resource_pools,
    create_test_resource_pool,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
)


class TestResourcePoolApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        def _assert_resource_pools_in_list(
            resource_pools: ResourcePool,
            resource_pools_response: ResourcePoolsListResponse,
        ) -> None:
            resource_pools_response = next(
                filter(
                    lambda resource_pools_response: resource_pools.id
                    == resource_pools_response.id,
                    resource_pools_response.items,
                )
            )
            assert resource_pools.id == resource_pools_response.id
            assert resource_pools.name == resource_pools_response.name
            assert (
                resource_pools.description
                == resource_pools_response.description
            )

        async def create_pagination_test_resources(
            fixture: Fixture, size: int
        ) -> list[ResourcePool]:
            if size > 1:
                # remove one because we have to consider the default resource pool
                return await create_n_test_resource_pools(
                    fixture, size=size - 1
                )
            return []

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/resource_pools",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig(
                    response_type=ResourcePoolsListResponse,
                    assert_routine=_assert_resource_pools_in_list,
                    create_resources_routine=create_pagination_test_resources,
                    size_parameters=list(range(1, 10)),
                ),
            ),
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/resource_pools/1",
                user_role=UserRole.USER,
            ),
            EndpointDetails(
                method="POST",
                path=f"{V3_API_PREFIX}/resource_pools",
                user_role=UserRole.ADMIN,
            ),
            EndpointDetails(
                method="PATCH",
                path=f"{V3_API_PREFIX}/resource_pools/1",
                user_role=UserRole.ADMIN,
            ),
        ]

    async def test_get(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ) -> None:
        created_resource_pools = await create_test_resource_pool(fixture)
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/resource_pools/{created_resource_pools.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "ResourcePool",
            "id": created_resource_pools.id,
            "name": created_resource_pools.name,
            "description": created_resource_pools.description,
            "created": created_resource_pools.created.isoformat(),
            "updated": created_resource_pools.updated.isoformat(),
            "_embedded": None,
            "_links": {
                "self": {
                    "href": f"{V3_API_PREFIX}/resource_pools/{created_resource_pools.id}"
                }
            },
        }

    @pytest.mark.parametrize("id,error", [("100", 404), ("xyz", 422)])
    async def test_get_invalid(
        self,
        authenticated_user_api_client_v3: AsyncClient,
        id: str,
        error: int,
    ) -> None:
        response = await authenticated_user_api_client_v3.get(
            f"{V3_API_PREFIX}/resource_pools/{id}"
        )
        assert response.status_code == error
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == error

    async def test_create(
        self,
        authenticated_admin_api_client_v3: AsyncClient,
    ) -> None:
        resource_pool_request = ResourcePoolRequest(
            name="new_resource pool", description="new_pool_description"
        )
        response = await authenticated_admin_api_client_v3.post(
            f"{V3_API_PREFIX}/resource_pools",
            json=jsonable_encoder(resource_pool_request),
        )
        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0
        resource_pools_response = ResourcePoolResponse(**response.json())
        assert resource_pools_response.id > 1
        assert resource_pools_response.name == resource_pool_request.name
        assert (
            resource_pools_response.description
            == resource_pool_request.description
        )
        assert (
            resource_pools_response.hal_links.self.href
            == f"{V3_API_PREFIX}/resource_pools/{resource_pools_response.id}"
        )

    @pytest.mark.parametrize(
        "error_code,request_data",
        [
            (422, {"name": None}),
            (422, {"description": None}),
            (422, {"name": "", "description": "test"}),
            (422, {"name": "-my_pool", "description": "test"}),
            (422, {"name": "my$pool", "description": "test"}),
        ],
    )
    async def test_create_invalid(
        self,
        authenticated_admin_api_client_v3: AsyncClient,
        error_code: int,
        request_data: dict[str, str],
    ) -> None:
        response = await authenticated_admin_api_client_v3.post(
            f"{V3_API_PREFIX}/resource_pools", json=request_data
        )
        assert response.status_code == error_code

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == error_code

    async def test_patch(
        self,
        authenticated_admin_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        resource_pool = await create_test_resource_pool(fixture=fixture)
        patch_resource_pool_request = ResourcePoolPatchRequest(
            name="newname", description="new description"
        )
        response = await authenticated_admin_api_client_v3.patch(
            f"{V3_API_PREFIX}/resource_pools/{resource_pool.id}",
            json=jsonable_encoder(patch_resource_pool_request),
        )
        assert response.status_code == 200

        patch_resource_pool = ResourcePoolResponse(**response.json())
        assert patch_resource_pool.id == resource_pool.id
        assert patch_resource_pool.name == patch_resource_pool_request.name
        assert (
            patch_resource_pool.description
            == patch_resource_pool_request.description
        )
        assert patch_resource_pool.created.astimezone(
            timezone.utc
        ) == resource_pool.created.astimezone(timezone.utc)
        assert patch_resource_pool.updated.astimezone(
            timezone.utc
        ) >= resource_pool.updated.astimezone(timezone.utc)

        patch_resource_pool_request2 = ResourcePoolPatchRequest(
            description="new description"
        )
        response = await authenticated_admin_api_client_v3.patch(
            f"{V3_API_PREFIX}/resource_pools/{resource_pool.id}",
            json=jsonable_encoder(
                patch_resource_pool_request2, exclude_none=True
            ),
        )
        assert response.status_code == 200

        patch_resource_pool2 = ResourcePoolResponse(**response.json())
        assert patch_resource_pool2.id == resource_pool.id
        assert patch_resource_pool2.name == patch_resource_pool_request.name
        assert (
            patch_resource_pool2.description
            == patch_resource_pool_request2.description
        )
        assert patch_resource_pool2.created.astimezone(
            timezone.utc
        ) == patch_resource_pool.created.astimezone(timezone.utc)
        assert patch_resource_pool2.updated.astimezone(
            timezone.utc
        ) >= patch_resource_pool.updated.astimezone(timezone.utc)

    async def test_patch_unexisting(
        self,
        authenticated_admin_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        patch_resource_pool_request = ResourcePoolPatchRequest(
            name="newname", description="new description"
        )
        response = await authenticated_admin_api_client_v3.patch(
            f"{V3_API_PREFIX}/resource_pools/1000",
            json=jsonable_encoder(patch_resource_pool_request),
        )
        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.code == 404

    @pytest.mark.parametrize(
        "error_code,request_data",
        [
            (422, {"name": None}),
            (422, {"description": None}),
            (422, {"name": "", "description": "test"}),
            (422, {"name": None, "description": "test"}),
            (422, {"name": "-my_pool", "description": "test"}),
            (422, {"name": "my$pool", "description": "test"}),
        ],
    )
    async def test_patch_invalid(
        self,
        authenticated_admin_api_client_v3: AsyncClient,
        fixture: Fixture,
        error_code: int,
        request_data: dict[str, str],
    ) -> None:
        response = await authenticated_admin_api_client_v3.patch(
            f"{V3_API_PREFIX}/resource_pools/0", json=request_data
        )
        assert response.status_code == error_code
