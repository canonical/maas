from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.models.requests.resource_pools import (
    ResourcePoolRequest,
    ResourcePoolUpdateRequest,
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
        async def create_pagination_test_resources(
            fixture: Fixture, size: int
        ) -> list[ResourcePool]:
            # The default resource pool is created by the migrations
            # and it has the following timestamp hardcoded in the test sql dump,
            # see src/maasserver/testing/inital.maas_test.sql:12611
            ts = datetime(
                2021, 11, 19, 12, 40, 56, 904770, tzinfo=timezone.utc
            )
            created_resource_pools = [
                ResourcePool(
                    id=0,
                    name="default",
                    description="Default pool",
                    created=ts,
                    updated=ts,
                )
            ]
            if size > 1:
                created_resource_pools.extend(
                    await create_n_test_resource_pools(fixture, size - 1)
                )
            return created_resource_pools

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/resource_pools",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig[
                    ResourcePool, ResourcePoolsListResponse
                ](
                    response_type=ResourcePoolsListResponse,
                    create_resources_routine=create_pagination_test_resources,
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
                method="PUT",
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

    async def test_put(
        self,
        authenticated_admin_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        resource_pool = await create_test_resource_pool(fixture=fixture)
        update_resource_pool_request = ResourcePoolUpdateRequest(
            name="newname", description="new description"
        )
        response = await authenticated_admin_api_client_v3.put(
            f"{V3_API_PREFIX}/resource_pools/{resource_pool.id}",
            json=jsonable_encoder(update_resource_pool_request),
        )
        assert response.status_code == 200

        update_resource_pool = ResourcePoolResponse(**response.json())
        assert update_resource_pool.id == resource_pool.id
        assert update_resource_pool.name == update_resource_pool_request.name
        assert (
            update_resource_pool.description
            == update_resource_pool_request.description
        )
        assert update_resource_pool.created.astimezone(
            timezone.utc
        ) == resource_pool.created.astimezone(timezone.utc)
        assert update_resource_pool.updated.astimezone(
            timezone.utc
        ) >= resource_pool.updated.astimezone(timezone.utc)

        update_resource_pool_request2 = ResourcePoolUpdateRequest(
            name=update_resource_pool_request.name,
            description="new description",
        )
        response = await authenticated_admin_api_client_v3.put(
            f"{V3_API_PREFIX}/resource_pools/{resource_pool.id}",
            json=jsonable_encoder(
                update_resource_pool_request2, exclude_none=True
            ),
        )
        assert response.status_code == 200

        update_resource_pool2 = ResourcePoolResponse(**response.json())
        assert update_resource_pool2.id == resource_pool.id
        assert update_resource_pool2.name == update_resource_pool_request.name
        assert (
            update_resource_pool2.description
            == update_resource_pool_request2.description
        )
        assert update_resource_pool2.created.astimezone(
            timezone.utc
        ) == update_resource_pool.created.astimezone(timezone.utc)
        assert update_resource_pool2.updated.astimezone(
            timezone.utc
        ) >= update_resource_pool.updated.astimezone(timezone.utc)

    async def test_put_unexisting(
        self,
        authenticated_admin_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        update_resource_pool_request = ResourcePoolUpdateRequest(
            name="newname", description="new description"
        )
        response = await authenticated_admin_api_client_v3.put(
            f"{V3_API_PREFIX}/resource_pools/1000",
            json=jsonable_encoder(update_resource_pool_request),
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
    async def test_put_invalid(
        self,
        authenticated_admin_api_client_v3: AsyncClient,
        fixture: Fixture,
        error_code: int,
        request_data: dict[str, str],
    ) -> None:
        response = await authenticated_admin_api_client_v3.put(
            f"{V3_API_PREFIX}/resource_pools/0", json=request_data
        )
        assert response.status_code == error_code
