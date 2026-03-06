# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.entitlements import (
    EntitlementRequest,
)
from maasapiserver.v3.api.public.models.requests.usergroup_members import (
    UserGroupMemberRequest,
)
from maasapiserver.v3.api.public.models.requests.usergroups import (
    UserGroupRequest,
)
from maasapiserver.v3.api.public.models.responses.entitlements import (
    EntitlementResponse,
    EntitlementsListResponse,
)
from maasapiserver.v3.api.public.models.responses.usergroup_members import (
    UserGroupMembersListResponse,
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
from maasservicelayer.models.openfga_tuple import OpenFGATuple
from maasservicelayer.models.usergroup_members import UserGroupMember
from maasservicelayer.models.usergroups import UserGroup
from maasservicelayer.models.users import User
from maasservicelayer.services import ServiceCollectionV3, UsersService
from maasservicelayer.services.openfga_tuples import OpenFGATupleService
from maasservicelayer.services.resource_pools import ResourcePoolsService
from maasservicelayer.services.usergroups import (
    UserAlreadyInGroup,
    UserGroupNotFound,
    UserGroupsService,
)
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

TEST_USER = User(
    id=10,
    username="user1",
    password="pass",
    is_superuser=False,
    first_name="",
    last_name="",
    is_staff=False,
    is_active=True,
    date_joined=utcnow(),
    email="u1@example.com",
    last_login=None,
)


class TestUserGroupsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/groups"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1/members"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1/entitlements"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="POST", path=f"{self.BASE_PATH}/1/members"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1/members/10"),
            Endpoint(method="POST", path=f"{self.BASE_PATH}/1/entitlements"),
            Endpoint(
                method="DELETE",
                path=f"{self.BASE_PATH}/1/entitlements"
                "?resource_type=maas&resource_id=0"
                "&entitlement=can_edit_machines",
            ),
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

    # GET /groups/{group_id}/members
    async def test_list_members(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        services_mock.usergroups.list_usergroup_members.return_value = [
            UserGroupMember(
                id=10, group_id=1, username="user1", email="u1@test.com"
            ),
            UserGroupMember(
                id=20, group_id=1, username="user2", email="u2@test.com"
            ),
        ]

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/members"
        )
        assert response.status_code == 200
        members_response = UserGroupMembersListResponse(**response.json())
        assert len(members_response.items) == 2
        assert members_response.items[0].username == "user1"
        assert members_response.items[1].username == "user2"

    async def test_list_members_empty(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        services_mock.usergroups.list_usergroup_members.return_value = []

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/members"
        )
        assert response.status_code == 200
        members_response = UserGroupMembersListResponse(**response.json())
        assert len(members_response.items) == 0

    async def test_list_members_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = None

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/999/members"
        )
        assert response.status_code == 404

    # POST /groups/{group_id}/members
    async def test_add_member(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        member_request = UserGroupMemberRequest(user_id=10)
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = TEST_USER
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.add_user_to_group_by_id.return_value = None
        services_mock.usergroups.list_usergroup_members.return_value = [
            UserGroupMember(
                id=10, group_id=1, username="user1", email="u1@test.com"
            ),
        ]

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/members",
            json=jsonable_encoder(member_request),
        )
        assert response.status_code == 200

    async def test_add_member_group_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        member_request = UserGroupMemberRequest(user_id=10)
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = TEST_USER
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.add_user_to_group_by_id.side_effect = (
            UserGroupNotFound()
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/999/members",
            json=jsonable_encoder(member_request),
        )
        assert response.status_code == 404

    async def test_add_member_already_in_group(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        member_request = UserGroupMemberRequest(user_id=10)
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = TEST_USER
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.add_user_to_group_by_id.side_effect = (
            UserAlreadyInGroup()
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/1/members",
            json=jsonable_encoder(member_request),
        )
        assert response.status_code == 409

    # DELETE /groups/{group_id}/members/{user_id}
    async def test_remove_member(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        services_mock.usergroups.remove_user_from_group.return_value = None

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/members/10"
        )
        assert response.status_code == 204

    async def test_remove_member_group_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = None

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/999/members/10"
        )
        assert response.status_code == 404

    # GET /groups/{group_id}/entitlements
    async def test_list_entitlements(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.list_entitlements = AsyncMock(
            return_value=[
                OpenFGATuple(
                    object_type="maas",
                    object_id="0",
                    relation="can_edit_machines",
                    user="group:1#member",
                    user_type="userset",
                ),
                OpenFGATuple(
                    object_type="pool",
                    object_id="5",
                    relation="can_deploy_machines",
                    user="group:1#member",
                    user_type="userset",
                ),
            ]
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements"
        )
        assert response.status_code == 200
        result = EntitlementsListResponse(**response.json())
        assert len(result.items) == 2
        assert result.items[0].resource_type == "maas"
        assert result.items[0].entitlement == "can_edit_machines"
        assert result.items[1].resource_type == "pool"
        assert result.items[1].resource_id == 5
        assert result.items[1].entitlement == "can_deploy_machines"

    async def test_list_entitlements_empty(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.list_entitlements = AsyncMock(
            return_value=[]
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements"
        )
        assert response.status_code == 200
        result = EntitlementsListResponse(**response.json())
        assert len(result.items) == 0

    async def test_list_entitlements_group_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = None

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/999/entitlements"
        )
        assert response.status_code == 404

    # POST /groups/{group_id}/entitlements
    async def test_add_entitlement_maas(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        entitlement_request = EntitlementRequest(
            resource_type="maas",
            resource_id=0,
            entitlement="can_edit_machines",
        )
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.upsert = AsyncMock(
            return_value=OpenFGATuple(
                object_type="maas",
                object_id="0",
                relation="can_edit_machines",
                user="group:1#member",
                user_type="userset",
            )
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements",
            json=jsonable_encoder(entitlement_request),
        )
        assert response.status_code == 200
        result = EntitlementResponse(**response.json())
        assert result.resource_type == "maas"
        assert result.resource_id == 0
        assert result.entitlement == "can_edit_machines"

    async def test_add_entitlement_pool(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        entitlement_request = EntitlementRequest(
            resource_type="pool",
            resource_id=5,
            entitlement="can_edit_machines",
        )
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.exists = AsyncMock(return_value=True)
        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.upsert = AsyncMock(
            return_value=OpenFGATuple(
                object_type="pool",
                object_id="5",
                relation="can_edit_machines",
                user="group:1#member",
                user_type="userset",
            )
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements",
            json=jsonable_encoder(entitlement_request),
        )
        assert response.status_code == 200
        result = EntitlementResponse(**response.json())
        assert result.resource_type == "pool"
        assert result.resource_id == 5
        assert result.entitlement == "can_edit_machines"

    async def test_add_entitlement_group_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        entitlement_request = EntitlementRequest(
            resource_type="maas",
            resource_id=0,
            entitlement="can_edit_machines",
        )
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = None

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/999/entitlements",
            json=jsonable_encoder(entitlement_request),
        )
        assert response.status_code == 404

    async def test_add_entitlement_invalid_resource_type(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        entitlement_request = {
            "resource_type": "invalid",
            "resource_id": 0,
            "entitlement": "can_edit_machines",
        }
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements",
            json=entitlement_request,
        )
        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.code == 422

    async def test_add_entitlement_maas_invalid(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        entitlement_request = EntitlementRequest(
            resource_type="maas",
            resource_id=-1,  # should be 0 for maas entitlements
            entitlement="can_edit_machines",
        )
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements",
            json=jsonable_encoder(entitlement_request),
        )
        assert response.status_code == 400

    async def test_add_entitlement_pool_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        entitlement_request = EntitlementRequest(
            resource_type="pool",
            resource_id=999,
            entitlement="can_edit_machines",
        )
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        services_mock.resource_pools = Mock(ResourcePoolsService)
        services_mock.resource_pools.exists = AsyncMock(return_value=False)

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements",
            json=jsonable_encoder(entitlement_request),
        )
        assert response.status_code == 404

    async def test_add_entitlement_invalid_entitlement_name(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        entitlement_request = EntitlementRequest(
            resource_type="maas",
            resource_id=0,
            entitlement="nonexistent_entitlement",
        )
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements",
            json=jsonable_encoder(entitlement_request),
        )
        assert response.status_code == 400
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.code == 400

    # DELETE /groups/{group_id}/entitlements
    async def test_remove_entitlement_maas(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.delete_entitlement = AsyncMock(
            return_value=None
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements",
            params={
                "resource_type": "maas",
                "resource_id": 0,
                "entitlement": "can_edit_machines",
            },
        )
        assert response.status_code == 204
        services_mock.openfga_tuples.delete_entitlement.assert_called_once_with(
            TEST_GROUP.id, "can_edit_machines", "maas", 0
        )

    async def test_remove_entitlement_pool(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP
        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.delete_entitlement = AsyncMock(
            return_value=None
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements",
            params={
                "resource_type": "pool",
                "resource_id": 5,
                "entitlement": "can_edit_machines",
            },
        )
        assert response.status_code == 204
        services_mock.openfga_tuples.delete_entitlement.assert_called_once_with(
            TEST_GROUP.id, "can_edit_machines", "pool", 5
        )

    async def test_remove_entitlement_group_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = None

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/999/entitlements",
            params={
                "resource_type": "maas",
                "resource_id": 0,
                "entitlement": "can_edit_machines",
            },
        )
        assert response.status_code == 404

    async def test_remove_entitlement_invalid_resource_type(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements",
            params={
                "resource_type": "invalid",
                "resource_id": 0,
                "entitlement": "can_edit_machines",
            },
        )
        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.code == 422

    async def test_remove_entitlement_invalid_entitlement_name(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.get_by_id.return_value = TEST_GROUP

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/{TEST_GROUP.id}/entitlements",
            params={
                "resource_type": "maas",
                "resource_id": 0,
                "entitlement": "nonexistent",
            },
        )
        assert response.status_code == 400
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.code == 400
