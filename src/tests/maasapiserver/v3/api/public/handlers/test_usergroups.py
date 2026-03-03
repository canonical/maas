# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.usergroups import (
    UserGroupRequest,
)
from maasapiserver.v3.api.public.models.responses.usergroups import (
    UserGroupResponse,
    UserGroupsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.usergroups import UserGroup
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.usergroups import UserGroupsService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_GROUP = UserGroup(
    id=1,
    name="test_group",
    description="test_description",
    created=utcnow(),
    updated=utcnow(),
)


class TestUserGroupsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/groups"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    # GET /groups
    async def test_list_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.list.return_value = ListResult[UserGroup](
            items=[TEST_GROUP], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        groups_response = UserGroupsListResponse(**response.json())
        assert len(groups_response.items) == 1
        assert groups_response.total == 2
        assert groups_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_list_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.list.return_value = ListResult[UserGroup](
            items=[TEST_GROUP], total=1
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        groups_response = UserGroupsListResponse(**response.json())
        assert len(groups_response.items) == 1
        assert groups_response.total == 1
        assert groups_response.next is None

    # GET /groups/{group_id}
    async def test_get(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_GROUP.id}"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        group_response = UserGroupResponse(**response.json())
        assert group_response.id == TEST_GROUP.id
        assert group_response.name == TEST_GROUP.name

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = None
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/100")
        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    # POST /groups
    async def test_post_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        group_request = UserGroupRequest(
            name=TEST_GROUP.name, description=TEST_GROUP.description
        )
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.create.return_value = TEST_GROUP
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(group_request)
        )
        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0
        group_response = UserGroupResponse(**response.json())
        assert group_response.name == group_request.name
        assert group_response.description == group_request.description
        assert (
            group_response.hal_links.self.href
            == f"{self.BASE_PATH}/{group_response.id}"
        )

    async def test_post_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        group_request = UserGroupRequest(name="duplicate_group")
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.create.side_effect = AlreadyExistsException(
            details=[
                BaseExceptionDetail(
                    type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                    message="A resource with such identifiers already exist.",
                )
            ]
        )
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(group_request)
        )
        assert response.status_code == 409
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409

    # PUT /groups/{group_id}
    async def test_put(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        updated_group = UserGroup(
            id=TEST_GROUP.id,
            name="new_name",
            description="new_description",
            created=utcnow(),
            updated=utcnow(),
        )
        update_request = UserGroupRequest(
            name="new_name", description="new_description"
        )
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.update_by_id.return_value = updated_group

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/{TEST_GROUP.id}",
            json=jsonable_encoder(update_request),
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        group_response = UserGroupResponse(**response.json())
        assert group_response.name == "new_name"
        assert group_response.description == "new_description"

    async def test_put_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.update_by_id.return_value = None
        update_request = UserGroupRequest(name="new_name")
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/99",
            json=jsonable_encoder(update_request),
        )
        assert response.status_code == 404

    # DELETE /groups/{group_id}
    async def test_delete(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.delete_by_id.side_effect = None
        response = await mocked_api_client_admin.delete(f"{self.BASE_PATH}/1")
        assert response.status_code == 204

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.delete_by_id.side_effect = [
            PreconditionFailedException(
                details=[
                    BaseExceptionDetail(
                        type=ETAG_PRECONDITION_VIOLATION_TYPE,
                        message="The resource etag 'wrong' did not match 'correct'.",
                    )
                ]
            ),
            None,
        ]

        failed_response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/1",
            headers={"if-match": "wrong"},
        )
        assert failed_response.status_code == 412

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/1",
            headers={"if-match": "correct"},
        )
        assert response.status_code == 204
