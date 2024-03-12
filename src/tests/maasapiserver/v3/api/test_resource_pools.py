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
from maasapiserver.v3.constants import EXTERNAL_V3_API_PREFIX
from maasapiserver.v3.models.resource_pools import ResourcePool
from tests.fixtures.factories.resource_pools import (
    create_n_test_resource_pools,
    create_test_resource_pool,
)
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestResourcePoolApi:
    def _assert_resource_pools_in_list(
        self,
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
            resource_pools.description == resource_pools_response.description
        )

    @pytest.mark.parametrize("resource_pools_size", range(1, 3))
    async def test_list(
        self,
        resource_pools_size: int,
        api_client: AsyncClient,
        fixture: Fixture,
    ) -> None:
        created_resource_pools = await create_n_test_resource_pools(
            fixture, size=resource_pools_size
        )
        response = await api_client.get("/api/v3/resource_pools")
        assert response.status_code == 200

        resource_pools_response = ResourcePoolsListResponse(**response.json())
        assert resource_pools_response.kind == "ResourcePoolList"
        # Increment as the default resource pool is included in the count.
        assert resource_pools_response.total == resource_pools_size + 1
        assert len(resource_pools_response.items) == resource_pools_size + 1
        for resource_pools in created_resource_pools:
            self._assert_resource_pools_in_list(
                resource_pools, resource_pools_response
            )

    async def test_parametrised_list(
        self, api_client: AsyncClient, fixture: Fixture
    ) -> None:
        await create_n_test_resource_pools(fixture, size=9)

        for page in range(1, 6):
            response = await api_client.get(
                f"/api/v3/resource_pools?page={page}&size=2"
            )
            assert response.status_code == 200
            resource_pools_response = ResourcePoolsListResponse(
                **response.json()
            )
            assert resource_pools_response.kind == "ResourcePoolList"
            assert resource_pools_response.total == 10
            assert len(resource_pools_response.items) == 2

    @pytest.mark.parametrize(
        "page,size", [(1, 0), (0, 1), (-1, -1), (1, 1001)]
    )
    async def test_invalid_list(
        self, page: int, size: int, api_client: AsyncClient
    ) -> None:
        response = await api_client.get(
            f"/api/v3/resource_pools?page={page}&size={size}"
        )
        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_get(
        self, api_client: AsyncClient, fixture: Fixture
    ) -> None:
        created_resource_pools = await create_test_resource_pool(fixture)
        response = await api_client.get(
            f"/api/v3/resource_pools/{created_resource_pools.id}"
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
                    "href": f"{EXTERNAL_V3_API_PREFIX}/resource_pools/{created_resource_pools.id}"
                }
            },
        }

    @pytest.mark.parametrize("id,error", [("100", 404), ("xyz", 422)])
    async def test_get_invalid(
        self, api_client: AsyncClient, id: str, error: int
    ) -> None:
        response = await api_client.get(f"/api/v3/resource_pools/{id}")
        assert response.status_code == error
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == error

    async def test_create(self, api_client: AsyncClient) -> None:
        resource_pool_request = ResourcePoolRequest(
            name="new_resource pool", description="new_pool_description"
        )
        response = await api_client.post(
            "/api/v3/resource_pools",
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
            == f"{EXTERNAL_V3_API_PREFIX}/resource_pools/{resource_pools_response.id}"
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
        api_client: AsyncClient,
        error_code: int,
        request_data: dict[str, str],
    ) -> None:
        response = await api_client.post(
            "/api/v3/resource_pools", json=request_data
        )
        assert response.status_code == error_code

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == error_code

    async def test_patch(
        self,
        api_client: AsyncClient,
        fixture: Fixture,
    ) -> None:
        resource_pool = await create_test_resource_pool(fixture=fixture)
        patch_resource_pool_request = ResourcePoolPatchRequest(
            name="newname", description="new description"
        )
        response = await api_client.patch(
            f"/api/v3/resource_pools/{resource_pool.id}",
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
        response = await api_client.patch(
            f"/api/v3/resource_pools/{resource_pool.id}",
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
        api_client: AsyncClient,
        fixture: Fixture,
    ) -> None:
        patch_resource_pool_request = ResourcePoolPatchRequest(
            name="newname", description="new description"
        )
        response = await api_client.patch(
            "/api/v3/resource_pools/1000",
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
        api_client: AsyncClient,
        fixture: Fixture,
        error_code: int,
        request_data: dict[str, str],
    ) -> None:
        response = await api_client.patch(
            "/api/v3/resource_pools/0", json=request_data
        )
        assert response.status_code == error_code
