#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timezone
from unittest.mock import AsyncMock, Mock

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.requests.resource_pools import (
    ResourcePoolRequest,
    ResourcePoolUpdateRequest,
)
from maasapiserver.v3.api.public.models.responses.resource_pools import (
    ResourcePoolResponse,
    ResourcePoolsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.resource_pools import ResourcePool
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.resource_pools import ResourcePoolsService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_RESOURCE_POOL = ResourcePool(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="test_resource_pool",
    description="test_description",
)
TEST_RESOURCE_POOL_2 = ResourcePool(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    name="test_resource_pool_2",
    description="test_description_2",
)


class TestResourcePoolApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/resource_pools"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=self.BASE_PATH),
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1"),
        ]

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.list = AsyncMock(
            return_value=ListResult[ResourcePool](
                items=[TEST_RESOURCE_POOL], next_token=None
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        resource_pools_response = ResourcePoolsListResponse(**response.json())
        assert len(resource_pools_response.items) == 1
        assert resource_pools_response.next is None

    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.list = AsyncMock(
            return_value=ListResult[ResourcePool](
                items=[TEST_RESOURCE_POOL_2],
                next_token=str(TEST_RESOURCE_POOL.id),
            )
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        resource_pools_response = ResourcePoolsListResponse(**response.json())
        assert len(resource_pools_response.items) == 1
        assert (
            resource_pools_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_RESOURCE_POOL.id), size='1')}"
        )

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.get_by_id = AsyncMock(
            return_value=(TEST_RESOURCE_POOL)
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_RESOURCE_POOL.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "ResourcePool",
            "id": TEST_RESOURCE_POOL.id,
            "name": TEST_RESOURCE_POOL.name,
            "description": TEST_RESOURCE_POOL.description,
            "created": TEST_RESOURCE_POOL.created.isoformat(),
            "updated": TEST_RESOURCE_POOL.updated.isoformat(),
            "_embedded": None,
            "_links": {
                "self": {"href": f"{self.BASE_PATH}/{TEST_RESOURCE_POOL.id}"}
            },
        }

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.get_by_id = AsyncMock(return_value=None)
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/100")
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_get_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.get_by_id = AsyncMock(
            side_effect=(RequestValidationError(errors=[]))
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_post_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        resource_pool_request = ResourcePoolRequest(
            name=TEST_RESOURCE_POOL.name,
            description=TEST_RESOURCE_POOL.description,
        )
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.create = AsyncMock(
            return_value=TEST_RESOURCE_POOL
        )
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(resource_pool_request)
        )
        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0
        resource_pools_response = ResourcePoolResponse(**response.json())
        assert resource_pools_response.id == TEST_RESOURCE_POOL.id
        assert resource_pools_response.name == resource_pool_request.name
        assert (
            resource_pools_response.description
            == resource_pool_request.description
        )
        assert (
            resource_pools_response.hal_links.self.href
            == f"{self.BASE_PATH}/{resource_pools_response.id}"
        )

    @pytest.mark.parametrize(
        "resource_pool_request",
        [
            {"name": None},
            {"description": None},
            {"name": "", "description": "test"},
            {"name": "-my_pool", "description": "test"},
            {"name": "my$pool", "description": "test"},
        ],
    )
    async def test_post_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        resource_pool_request: dict[str, str],
    ) -> None:
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.create = AsyncMock(
            side_effect=ValueError("Invalid entity name.")
        )
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=resource_pool_request
        )
        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        updated_rp = TEST_RESOURCE_POOL
        updated_rp.name = "newname"
        updated_rp.description = "new description"
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.update = AsyncMock(
            return_value=updated_rp
        )
        update_resource_pool_request = ResourcePoolUpdateRequest(
            name="newname", description="new description"
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{str(TEST_RESOURCE_POOL.id)}",
            json=jsonable_encoder(update_resource_pool_request),
        )
        assert response.status_code == 200

        update_resource_pool = ResourcePoolResponse(**response.json())
        assert update_resource_pool.id == TEST_RESOURCE_POOL.id
        assert update_resource_pool.name == update_resource_pool_request.name
        assert (
            update_resource_pool.description
            == update_resource_pool_request.description
        )
        assert update_resource_pool.created.astimezone(
            timezone.utc
        ) == TEST_RESOURCE_POOL.created.astimezone(timezone.utc)
        assert update_resource_pool.updated.astimezone(
            timezone.utc
        ) >= TEST_RESOURCE_POOL.updated.astimezone(timezone.utc)

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.update = AsyncMock(
            side_effect=NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message="Resource pool with id 1000 does not exist.",
                    )
                ]
            )
        )
        update_resource_pool_request = ResourcePoolUpdateRequest(
            name="newname", description="new description"
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1000",
            json=jsonable_encoder(update_resource_pool_request),
        )

        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.code == 404

    @pytest.mark.parametrize(
        "resource_pool_request",
        [
            {"name": None},
            {"description": None},
            {"name": "", "description": "test"},
            {"name": None, "description": "test"},
            {"name": "-my_pool", "description": "test"},
            {"name": "my$pool", "description": "test"},
        ],
    )
    async def test_put_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        resource_pool_request: dict[str, str],
    ) -> None:
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.update = AsyncMock(
            side_effect=(RequestValidationError(errors=[]))
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1", json=resource_pool_request
        )
        assert response.status_code == 422
