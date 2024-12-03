#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

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
from maasservicelayer.auth.macaroons.macaroon_client import RbacAsyncClient
from maasservicelayer.auth.macaroons.models.responses import (
    PermissionResourcesMapping,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolClauseFactory,
)
from maasservicelayer.enums.rbac import RbacPermission
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.resource_pools import ResourcePool
from maasservicelayer.services import ExternalAuthService, ServiceCollectionV3
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
        services_mock.resource_pools.list.return_value = ListResult[
            ResourcePool
        ](items=[TEST_RESOURCE_POOL], next_token=None)
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
        services_mock.resource_pools.list.return_value = ListResult[
            ResourcePool
        ](
            items=[TEST_RESOURCE_POOL_2],
            next_token=str(TEST_RESOURCE_POOL.id),
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        resource_pools_response = ResourcePoolsListResponse(**response.json())
        assert len(resource_pools_response.items) == 1
        assert (
            resource_pools_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(TEST_RESOURCE_POOL.id), size='1')}"
        )

    async def test_list_with_rbac(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_rbac: AsyncClient,
    ) -> None:
        services_mock.external_auth = Mock(ExternalAuthService)

        rbac_client_mock = Mock(RbacAsyncClient)

        rbac_client_mock.get_resource_pool_ids.return_value = [
            PermissionResourcesMapping(
                permission=RbacPermission.VIEW, resources=[1, 2]
            ),
            PermissionResourcesMapping(
                permission=RbacPermission.VIEW_ALL, resources=[1]
            ),
        ]
        services_mock.external_auth.get_rbac_client.return_value = (
            rbac_client_mock
        )

        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.list.return_value = ListResult[
            ResourcePool
        ](
            items=[TEST_RESOURCE_POOL, TEST_RESOURCE_POOL_2],
            next_token=None,
        )
        response = await mocked_api_client_user_rbac.get(f"{self.BASE_PATH}")
        assert response.status_code == 200
        resource_pools_response = ResourcePoolsListResponse(**response.json())
        assert len(resource_pools_response.items) == 2

        rbac_client_mock.get_resource_pool_ids.assert_called_once_with(
            user="username",
            permissions={RbacPermission.VIEW, RbacPermission.VIEW_ALL},
        )
        services_mock.resource_pools.list.assert_called_once_with(
            token=None,
            size=20,
            query=QuerySpec(where=ResourcePoolClauseFactory.with_ids([1, 2])),
        )

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.get_by_id.return_value = (
            TEST_RESOURCE_POOL
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
        services_mock.resource_pools.get_by_id.return_value = None
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
        services_mock.resource_pools.get_by_id.side_effect = (
            RequestValidationError(errors=[])
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_get_with_rbac(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_rbac: AsyncClient,
    ) -> None:
        services_mock.external_auth = Mock(ExternalAuthService)

        rbac_client_mock = Mock(RbacAsyncClient)

        rbac_client_mock.get_resource_pool_ids.return_value = [
            PermissionResourcesMapping(
                # can access only
                permission=RbacPermission.VIEW,
                resources=[1],
            ),
        ]
        services_mock.external_auth.get_rbac_client.return_value = (
            rbac_client_mock
        )

        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.get_by_id.return_value = (
            TEST_RESOURCE_POOL
        )
        response = await mocked_api_client_user_rbac.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200
        resource_pool_response = ResourcePoolResponse(**response.json())
        assert resource_pool_response.id == 1

        rbac_client_mock.get_resource_pool_ids.assert_called_once_with(
            user="username",
            permissions={RbacPermission.VIEW},
        )
        services_mock.resource_pools.get_by_id.assert_called_once_with(1)

        # The user can't access the resource pool 2
        response = await mocked_api_client_user_rbac.get(f"{self.BASE_PATH}/2")
        assert response.status_code == 403

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
        services_mock.resource_pools.create.return_value = TEST_RESOURCE_POOL
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
        services_mock.resource_pools.create.side_effect = ValueError(
            "Invalid entity name."
        )
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=resource_pool_request
        )
        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_post_with_rbac(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin_rbac: AsyncClient,
    ) -> None:
        services_mock.external_auth = Mock(ExternalAuthService)

        rbac_client_mock = Mock(RbacAsyncClient)

        rbac_client_mock.get_resource_pool_ids.return_value = [
            PermissionResourcesMapping(
                permission=RbacPermission.EDIT, resources=[""]
            ),
        ]
        services_mock.external_auth.get_rbac_client.return_value = (
            rbac_client_mock
        )

        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.create.return_value = TEST_RESOURCE_POOL

        resource_pool_request = ResourcePoolRequest(
            name=TEST_RESOURCE_POOL.name,
            description=TEST_RESOURCE_POOL.description,
        )
        response = await mocked_api_client_admin_rbac.post(
            self.BASE_PATH, json=jsonable_encoder(resource_pool_request)
        )
        assert response.status_code == 201

        rbac_client_mock.get_resource_pool_ids.assert_called_once_with(
            user="username",
            permissions={RbacPermission.EDIT},
        )

    async def test_post_with_rbac_forbidden(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin_rbac: AsyncClient,
    ) -> None:
        services_mock.external_auth = Mock(ExternalAuthService)

        rbac_client_mock = Mock(RbacAsyncClient)

        rbac_client_mock.get_resource_pool_ids.return_value = [
            PermissionResourcesMapping(
                # The user can create resources only if [""] (alias ALL resources) is set
                permission=RbacPermission.EDIT,
                resources=[1],
            ),
        ]
        services_mock.external_auth.get_rbac_client.return_value = (
            rbac_client_mock
        )

        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.create.return_value = TEST_RESOURCE_POOL

        resource_pool_request = ResourcePoolRequest(
            name=TEST_RESOURCE_POOL.name,
            description=TEST_RESOURCE_POOL.description,
        )
        response = await mocked_api_client_admin_rbac.post(
            self.BASE_PATH, json=jsonable_encoder(resource_pool_request)
        )
        assert response.status_code == 403

        rbac_client_mock.get_resource_pool_ids.assert_called_once_with(
            user="username",
            permissions={RbacPermission.EDIT},
        )

    async def test_put_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        updated_rp = TEST_RESOURCE_POOL
        updated_rp.name = "newname"
        updated_rp.description = "new description"
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.update_by_id.return_value = updated_rp
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

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.update_by_id.side_effect = (
            NotFoundException(
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
        services_mock.resource_pools.update_by_id.side_effect = (
            RequestValidationError(errors=[])
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1", json=resource_pool_request
        )
        assert response.status_code == 422

    async def test_put_with_rbac(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin_rbac: AsyncClient,
    ) -> None:
        services_mock.external_auth = Mock(ExternalAuthService)

        rbac_client_mock = Mock(RbacAsyncClient)

        rbac_client_mock.get_resource_pool_ids.return_value = [
            PermissionResourcesMapping(
                permission=RbacPermission.EDIT, resources=[1]
            ),
        ]
        services_mock.external_auth.get_rbac_client.return_value = (
            rbac_client_mock
        )

        updated_rp = TEST_RESOURCE_POOL
        updated_rp.name = "newname"
        updated_rp.description = "new description"

        services_mock.resource_pools = Mock(ResourcePoolsService)

        services_mock.resource_pools.update_by_id.return_value = updated_rp
        update_resource_pool_request = ResourcePoolUpdateRequest(
            name="newname", description="new description"
        )
        response = await mocked_api_client_admin_rbac.put(
            f"{self.BASE_PATH}/{str(TEST_RESOURCE_POOL.id)}",
            json=jsonable_encoder(update_resource_pool_request),
        )

        assert response.status_code == 200

        rbac_client_mock.get_resource_pool_ids.assert_called_once_with(
            user="username",
            permissions={RbacPermission.EDIT},
        )

        # The user can't access the resource pool 2
        response = await mocked_api_client_admin_rbac.put(
            f"{self.BASE_PATH}/2",
            json=jsonable_encoder(update_resource_pool_request),
        )
        assert response.status_code == 403
