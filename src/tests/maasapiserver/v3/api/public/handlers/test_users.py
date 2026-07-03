# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json
from json import dumps as _dumps
from typing import Callable
from unittest.mock import call, Mock, patch

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
from macaroonbakery.bakery import Macaroon
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.users import (
    UserCreateRequest,
    UserUpdateRequest,
)
from maasapiserver.v3.api.public.models.responses.users import (
    UserInfoResponse,
    UserResponse,
    UsersListResponse,
    UsersStatisticsListResponse,
    UserStatisticsResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.users import UserClauseFactory
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadRequestException,
    BaseExceptionDetail,
    DischargeRequiredException,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
    INVALID_ARGUMENT_VIOLATION_TYPE,
    PRECONDITION_FAILED,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.openfga_tuple import OpenFGATuple
from maasservicelayer.models.usergroups import UserGroup, UserGroupsByUser
from maasservicelayer.models.users import User, UserProfile, UserStatistics
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.external_auth import ExternalAuthService
from maasservicelayer.services.openfga_tuples import OpenFGATupleService
from maasservicelayer.services.usergroups import (
    UserGroupNotFound,
    UserGroupsService,
)
from maasservicelayer.services.users import UsersService
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

USER_1 = User(
    id=1,
    username="username",
    password="pass",
    is_superuser=False,
    first_name="",
    last_name="",
    is_staff=False,
    is_active=True,
    date_joined=utcnow(),
    email="username@example.com",
    last_login=None,
)

USER_2 = User(
    id=2,
    username="username2",
    password="pass2",
    is_superuser=False,
    first_name="Bob",
    last_name="Guy",
    is_staff=False,
    is_active=True,
    date_joined=utcnow(),
    email="bob@company.com",
    last_login=None,
)

GROUP_1 = UserGroup(
    id=10,
    name="admins",
    description="Admins",
    created=utcnow(),
    updated=utcnow(),
)

GROUP_2 = UserGroup(
    id=20,
    name="viewers",
    description="Viewers",
    created=utcnow(),
    updated=utcnow(),
)


@pytest.mark.asyncio
class TestUsersApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/users"

    @pytest.fixture
    def endpoints_with_authorization(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}",
                permission=MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
            ),
            Endpoint(
                method="GET",
                path=f"{V3_API_PREFIX}/users:statistics",
                permission=MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
            ),
            Endpoint(
                method="POST",
                path=f"{self.BASE_PATH}",
                permission=MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
            ),
            Endpoint(
                method="PUT",
                path=f"{self.BASE_PATH}/1",
                permission=MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
            ),
            Endpoint(
                method="DELETE",
                path=f"{self.BASE_PATH}/1",
                permission=MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
            ),
            Endpoint(
                method="POST",
                path=f"{self.BASE_PATH}/1:change_password",
                permission=MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
            ),
        ]

    @pytest.fixture
    def endpoints_with_authentication_only(self) -> list[Endpoint]:
        return [
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/me",
            ),
            Endpoint(
                method="GET",
                path=f"{self.BASE_PATH}/1",
                permission=MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
            ),
            Endpoint(
                method="POST",
                path=f"{self.BASE_PATH}/me:complete_intro",
            ),
            Endpoint(
                method="POST",
                path=f"{self.BASE_PATH}/me:change_password",
            ),
        ]

    # GET /users/me
    async def test_get_user_info(
        self, services_mock: ServiceCollectionV3, mocked_api_client_user
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.get_one.return_value = User(
            id=1,
            username="username",
            password="pass",
            is_superuser=False,
            first_name="",
            last_name="",
            is_staff=False,
            is_active=True,
            date_joined=utcnow(),
            email=None,
            last_login=None,
        )
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={1: [GROUP_1, GROUP_2]})
        )
        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.list_entitlements_for_groups.return_value = [
            OpenFGATuple(
                object_type="maas",
                object_id="0",
                relation="can_view_machines",
                user="group:10#member",
                user_type="userset",
            ),
            # duplicate from another group, must be deduplicated
            OpenFGATuple(
                object_type="maas",
                object_id="0",
                relation="can_view_machines",
                user="group:20#member",
                user_type="userset",
            ),
            OpenFGATuple(
                object_type="pool",
                object_id="1",
                relation="can_edit_machines",
                user="group:20#member",
                user_type="userset",
            ),
        ]
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/me",
        )
        assert response.status_code == 200

        user_info = UserInfoResponse(**response.json())
        assert user_info.id == 1
        assert user_info.username == "username"
        assert {
            (e.resource_type, e.resource_id, e.entitlement)
            for e in user_info.entitlements
        } == {
            ("maas", 0, "can_view_machines"),
            ("pool", 1, "can_edit_machines"),
        }
        services_mock.openfga_tuples.list_entitlements_for_groups.assert_called_once_with(
            [GROUP_1.id, GROUP_2.id]
        )

    async def test_get_user_info_no_groups(
        self, services_mock: ServiceCollectionV3, mocked_api_client_user
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.get_one.return_value = USER_1
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={})
        )
        services_mock.openfga_tuples = Mock(OpenFGATupleService)
        services_mock.openfga_tuples.list_entitlements_for_groups.return_value = []
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/me",
        )
        assert response.status_code == 200

        user_info = UserInfoResponse(**response.json())
        assert user_info.entitlements == []
        services_mock.openfga_tuples.list_entitlements_for_groups.assert_called_once_with(
            []
        )

    async def test_get_user_info_unauthorized(
        self, mocked_api_client: AsyncClient
    ) -> None:
        response = await mocked_api_client.get(f"{self.BASE_PATH}/me")
        assert response.status_code == 401
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 401

    async def test_get_user_info_discharge_required(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_rbac: AsyncClient,
    ) -> None:
        """If external auth is enabled make sure we receive a discharge required response"""
        services_mock.external_auth = Mock(ExternalAuthService)
        services_mock.external_auth.raise_discharge_required_exception.side_effect = DischargeRequiredException(
            macaroon=Mock(Macaroon)
        )

        # we have to mock json.dumps as it doesn't know how to deal with Mock objects
        def custom_json_dumps(*args, **kwargs):
            return _dumps(*args, **(kwargs | {"default": lambda obj: "mock"}))

        with patch("json.dumps", custom_json_dumps):
            response = await mocked_api_client_rbac.get(f"{self.BASE_PATH}/me")

        assert response.status_code == 401
        discharge_response = json.loads(response.content.decode("utf-8"))
        assert discharge_response["Code"] == "macaroon discharge required"
        assert discharge_response["Info"]["Macaroon"] is not None
        assert discharge_response["Info"]["MacaroonPath"] == "/"
        assert discharge_response["Info"]["CookieNameSuffix"] == "maas"

    # GET /users
    async def test_list_users_has_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.list.return_value = ListResult[User](
            items=[USER_1], total=2
        )
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={USER_1.id: [GROUP_1, GROUP_2]})
        )
        response = await client.get(
            f"{self.BASE_PATH}?size=1",
        )

        assert response.status_code == 200
        users_response = UsersListResponse(**response.json())
        assert len(users_response.items) == 1
        assert users_response.total == 2
        assert users_response.next == f"{self.BASE_PATH}?page=2&size=1"
        assert [(g.id, g.name) for g in users_response.items[0].groups] == [
            (GROUP_1.id, GROUP_1.name),
            (GROUP_2.id, GROUP_2.name),
        ]
        services_mock.users.get_groups_for_users.assert_called_once_with(
            [USER_1.id]
        )

    async def test_list_users_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.list.return_value = ListResult[User](
            items=[USER_1, USER_2], total=2
        )
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(
                groups_by_user={USER_1.id: [GROUP_1], USER_2.id: []}
            )
        )
        response = await client.get(
            f"{self.BASE_PATH}?size=2",
        )

        assert response.status_code == 200
        users_response = UsersListResponse(**response.json())
        assert len(users_response.items) == 2
        assert users_response.total == 2
        assert users_response.next is None
        assert [(g.id, g.name) for g in users_response.items[0].groups] == [
            (GROUP_1.id, GROUP_1.name)
        ]
        assert users_response.items[1].groups == []

    async def test_list_users_with_username_or_email_filter(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.list.return_value = ListResult[User](
            items=[USER_1], total=2
        )
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={USER_1.id: []})
        )

        response = await client.get(
            f"{self.BASE_PATH}?size=1&username_or_email=example",
        )
        assert response.status_code == 200
        users_response = UsersListResponse(**response.json())
        assert users_response.total == 2
        assert len(users_response.items) == 1
        assert (
            users_response.next
            == f"{self.BASE_PATH}?page=2&size=1&username_or_email=example"
        )
        services_mock.users.list.assert_called_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=UserClauseFactory.with_username_or_email_like("example")
            ),
        )

    # GET /users/{user_id}
    async def test_get_user_can_view_identities(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = USER_1
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={USER_1.id: [GROUP_1]})
        )
        response = await client.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        user_response = UserResponse(**response.json())
        assert user_response.id == 1
        assert user_response.username == "username"
        assert [(g.id, g.name) for g in user_response.groups] == [
            (GROUP_1.id, GROUP_1.name)
        ]
        services_mock.users.get_groups_for_users.assert_called_once_with(
            [USER_1.id]
        )

    async def test_get_other_user_no_entitlement(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        # no permissions on openfga
        client = mocked_api_client_user_with_permissions()
        services_mock.users = Mock(UsersService)
        # the user we use in tests has the id=0
        response = await client.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404
        services_mock.users.get_by_id.assert_not_called()
        services_mock.users.get_groups_for_users.assert_not_called()

    async def test_get_self_user_no_entitlement(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        # no permissions on openfga
        client = mocked_api_client_user_with_permissions()
        user = USER_1.model_copy()
        # the user we use in tests has the id=0
        user.id = 0
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = user
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={user.id: [GROUP_1]})
        )
        response = await client.get(f"{self.BASE_PATH}/0")
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        user_response = UserResponse(**response.json())
        assert user_response.id == 0
        assert user_response.username == "username"
        assert [(g.id, g.name) for g in user_response.groups] == [
            (GROUP_1.id, GROUP_1.name)
        ]
        services_mock.users.get_groups_for_users.assert_called_once_with(
            [user.id]
        )

    async def test_get_user_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = None
        response = await client.get(f"{self.BASE_PATH}/99")
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_get_user_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.side_effect = RequestValidationError(
            errors=[]
        )
        response = await client.get(f"{self.BASE_PATH}/1a")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    # POST /users/{user_id}
    async def test_post_user(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        create_user_request = UserCreateRequest(
            username="new_username",
            password="new_password",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_user@example.com",
        )
        new_user = User(
            id=3,
            username="new_username",
            password="new_password",
            is_superuser=False,
            is_staff=False,
            is_active=False,
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_user@example.com",
            date_joined=utcnow(),
        )

        services_mock.users = Mock(UsersService)
        services_mock.users.create.return_value = new_user
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={new_user.id: []})
        )
        services_mock.usergroups = Mock(UserGroupsService)

        response = await client.post(
            self.BASE_PATH, json=jsonable_encoder(create_user_request)
        )

        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0

        user_response = UserResponse(**response.json())

        assert user_response.id == new_user.id
        assert user_response.groups == []
        assert user_response.username == new_user.username
        assert user_response.first_name == new_user.first_name
        assert user_response.last_name == new_user.last_name
        assert user_response.email == new_user.email
        assert user_response.date_joined == new_user.date_joined
        services_mock.usergroups.add_user_to_group_by_id.assert_not_called()

    async def test_post_user_with_groups(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        create_user_request = UserCreateRequest(
            username="new_username",
            password="new_password",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_user@example.com",
            groups=[GROUP_1.id, GROUP_2.id, GROUP_1.id],
        )
        new_user = User(
            id=3,
            username="new_username",
            password="new_password",
            is_superuser=False,
            is_staff=False,
            is_active=False,
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_user@example.com",
            date_joined=utcnow(),
        )

        services_mock.users = Mock(UsersService)
        services_mock.users.create.return_value = new_user
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={new_user.id: [GROUP_1, GROUP_2]})
        )
        services_mock.usergroups = Mock(UserGroupsService)

        response = await client.post(
            self.BASE_PATH, json=jsonable_encoder(create_user_request)
        )

        assert response.status_code == 201
        user_response = UserResponse(**response.json())
        assert [(g.id, g.name) for g in user_response.groups] == [
            (GROUP_1.id, GROUP_1.name),
            (GROUP_2.id, GROUP_2.name),
        ]
        # Duplicate group ids are de-duplicated.
        assert (
            services_mock.usergroups.add_user_to_group_by_id.await_args_list
            == [
                call(new_user.id, GROUP_1.id),
                call(new_user.id, GROUP_2.id),
            ]
        )

    async def test_post_user_with_unknown_group(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        create_user_request = UserCreateRequest(
            username="new_username",
            password="new_password",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_user@example.com",
            groups=[GROUP_1.id],
        )
        new_user = User(
            id=3,
            username="new_username",
            password="new_password",
            is_superuser=False,
            is_staff=False,
            is_active=False,
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_user@example.com",
            date_joined=utcnow(),
        )

        services_mock.users = Mock(UsersService)
        services_mock.users.create.return_value = new_user
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.add_user_to_group_by_id.side_effect = (
            UserGroupNotFound()
        )

        response = await client.post(
            self.BASE_PATH, json=jsonable_encoder(create_user_request)
        )

        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_post_user_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        create_user_request = UserCreateRequest(
            username="new_username",
            password="new_password",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_user@example.com",
        )
        new_user = User(
            id=3,
            username="new_username",
            password="new_password",
            is_superuser=False,
            is_staff=False,
            is_active=False,
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_user@example.com",
            date_joined=utcnow(),
        )

        services_mock.users = Mock(UsersService)
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={new_user.id: []})
        )
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.users.create.side_effect = [
            new_user,
            AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                        message="A resource with such identifiers already exist.",
                    )
                ]
            ),
        ]

        response = await client.post(
            self.BASE_PATH, json=jsonable_encoder(create_user_request)
        )
        assert response.status_code == 201

        response = await client.post(
            self.BASE_PATH, json=jsonable_encoder(create_user_request)
        )
        assert response.status_code == 409

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409
        assert len(error_response.details) == 1
        assert error_response.details[0].type == "UniqueConstraintViolation"
        assert "already exist" in error_response.details[0].message

    @pytest.mark.parametrize("user_request", [{"username": None}])
    async def test_post_user_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
        user_request: dict[str, str],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.create.return_value = None

        response = await client.post(
            self.BASE_PATH, json=jsonable_encoder(user_request)
        )

        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 422

    # PUT /users/{user_id}
    async def test_put_user(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        updated_user = User(
            id=1,
            is_active=False,
            is_superuser=True,
            is_staff=False,
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.update_by_id.return_value = updated_user
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={updated_user.id: []})
        )
        services_mock.usergroups = Mock(UserGroupsService)

        user_request = UserUpdateRequest(
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
        )

        response = await client.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(user_request),
        )

        assert response.status_code == 200

        user_response = UserResponse(**response.json())

        assert user_response.id == updated_user.id
        assert user_response.groups == []
        assert user_response.username == updated_user.username
        assert user_response.first_name == updated_user.first_name
        assert user_response.last_name == updated_user.last_name
        assert user_response.email == updated_user.email

    async def test_put_user_reconciles_groups(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        updated_user = User(
            id=1,
            is_active=False,
            is_superuser=False,
            is_staff=False,
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.update_by_id.return_value = updated_user
        # The user currently belongs to GROUP_1, and we request GROUP_2.
        services_mock.users.get_groups_for_users.side_effect = [
            UserGroupsByUser(groups_by_user={updated_user.id: [GROUP_1]}),
            UserGroupsByUser(groups_by_user={updated_user.id: [GROUP_2]}),
        ]
        services_mock.usergroups = Mock(UserGroupsService)

        user_request = UserUpdateRequest(
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
            groups=[GROUP_2.id],
        )

        response = await client.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(user_request),
        )

        assert response.status_code == 200
        user_response = UserResponse(**response.json())
        assert [(g.id, g.name) for g in user_response.groups] == [
            (GROUP_2.id, GROUP_2.name)
        ]
        services_mock.usergroups.add_user_to_group_by_id.assert_awaited_once_with(
            updated_user.id, GROUP_2.id
        )
        services_mock.usergroups.remove_user_from_group.assert_awaited_once_with(
            GROUP_1.id, updated_user.id
        )

    async def test_put_user_with_unknown_group(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        updated_user = User(
            id=1,
            is_active=False,
            is_superuser=False,
            is_staff=False,
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.update_by_id.return_value = updated_user
        services_mock.users.get_groups_for_users.return_value = (
            UserGroupsByUser(groups_by_user={updated_user.id: []})
        )
        services_mock.usergroups = Mock(UserGroupsService)
        services_mock.usergroups.add_user_to_group_by_id.side_effect = (
            UserGroupNotFound()
        )

        user_request = UserUpdateRequest(
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
            groups=[GROUP_1.id],
        )

        response = await client.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(user_request),
        )

        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_put_user_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.update_by_id.side_effect = NotFoundException()

        user_request = UserUpdateRequest(
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
        )

        response = await client.put(
            f"{self.BASE_PATH}/99",
            json=jsonable_encoder(user_request),
        )

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_put_user_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.update_by_id.return_value = None

        user_request = UserUpdateRequest(
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
        )

        response = await client.put(
            f"{self.BASE_PATH}/A1",
            json=jsonable_encoder(user_request),
        )

        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_delete_204(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = USER_1
        services_mock.users.delete_by_id.return_value = USER_1

        response = await client.delete(f"{self.BASE_PATH}/1")
        assert response.status_code == 204

    async def test_delete_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.exists.return_value = False

        response = await client.delete(f"{self.BASE_PATH}/1")
        assert response.status_code == 404

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.exists.return_value = True
        services_mock.users.delete_by_id.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message="The resource etag 'wrong_etag' did not match 'my_etag'.",
                )
            ]
        )

        response = await client.delete(
            f"{self.BASE_PATH}/1", headers={"if-match": "wrong_etag"}
        )
        assert response.status_code == 412
        services_mock.users.exists.assert_called_with(
            query=QuerySpec(UserClauseFactory.with_id(USER_1.id))
        )
        services_mock.users.delete_by_id.assert_called_with(
            USER_1.id,
            etag_if_match="wrong_etag",
        )

    async def test_delete_self(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        user = USER_1.model_copy()
        # the api client we use has an authenticated user with id=0
        user.id = 0
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = user

        response = await client.delete(f"{self.BASE_PATH}/0")
        assert response.status_code == 400

    async def test_delete_with_resources_allocated(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = USER_1
        services_mock.users.delete_by_id.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=PRECONDITION_FAILED,
                    message="Cannot delete user. 2 node(s) are still allocated.",
                )
            ]
        )
        response = await client.delete(f"{self.BASE_PATH}/1")
        assert response.status_code == 412

    async def test_delete_with_transfer_resources(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = USER_1
        services_mock.users.transfer_resources.return_value = None
        services_mock.users.delete_by_id.return_value = USER_1

        response = await client.delete(
            f"{self.BASE_PATH}/1", params={"transfer_resources_to": 2}
        )
        assert response.status_code == 204
        services_mock.users.transfer_resources.assert_called_once_with(1, 2)

    async def test_delete_with_transfer_resources_nonexistent_user(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = USER_1
        services_mock.users.transfer_resources.side_effect = BadRequestException(
            details=[
                BaseExceptionDetail(
                    type=INVALID_ARGUMENT_VIOLATION_TYPE,
                    message="Cannot transfer resources. User with id 2 doesn't exist.",
                )
            ]
        )

        response = await client.delete(
            f"{self.BASE_PATH}/1", params={"transfer_resources_to": 2}
        )
        assert response.status_code == 400
        services_mock.users.transfer_resources.assert_called_once_with(1, 2)

    async def test_list_statistics(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.list_statistics.return_value = ListResult[
            UserStatistics
        ](
            items=[
                UserStatistics(
                    id=1,
                    completed_intro=True,
                    is_local=True,
                    machines_count=2,
                    sshkeys_count=3,
                )
            ],
            total=1,
        )

        response = await client.get(
            f"{V3_API_PREFIX}/users:statistics?size=1",
        )
        assert response.status_code == 200
        users_statistics = UsersStatisticsListResponse(**response.json())
        assert users_statistics.total == 1
        assert len(users_statistics.items) == 1
        assert users_statistics.next is None
        user = users_statistics.items[0]
        assert user.id == 1
        assert user.completed_intro is True
        assert user.is_local is True
        assert user.machines_count == 2
        assert user.sshkeys_count == 3
        services_mock.users.list_statistics.assert_called_once_with(
            page=1, size=1, query=QuerySpec(where=None)
        )

    async def test_list_statistics_filters(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.list_statistics.return_value = ListResult[
            UserStatistics
        ](
            items=[
                UserStatistics(
                    id=1,
                    completed_intro=True,
                    is_local=True,
                    machines_count=2,
                    sshkeys_count=3,
                )
            ],
            total=2,
        )

        response = await client.get(
            f"{V3_API_PREFIX}/users:statistics?size=1&username_or_email=example",
        )
        assert response.status_code == 200
        users_statistics = UsersStatisticsListResponse(**response.json())
        assert users_statistics.total == 2
        assert len(users_statistics.items) == 1
        assert (
            users_statistics.next
            == f"{V3_API_PREFIX}/users:statistics?page=2&size=1&username_or_email=example"
        )
        services_mock.users.list_statistics.assert_called_once_with(
            page=1,
            size=1,
            query=QuerySpec(
                where=UserClauseFactory.with_username_or_email_like("example")
            ),
        )

    async def test_complete_intro(
        self, services_mock: ServiceCollectionV3, mocked_api_client_user
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.complete_intro.return_value = Mock(UserProfile)

        response = await mocked_api_client_user.post(
            f"{V3_API_PREFIX}/users/me:complete_intro"
        )
        assert response.status_code == 204

        # the user we use in tests has the id=0
        services_mock.users.complete_intro.assert_called_once_with(0)

    async def test_change_password_user(
        self, services_mock: ServiceCollectionV3, mocked_api_client_user
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.change_password.return_value = None

        json = {"password": "foo"}

        response = await mocked_api_client_user.post(
            f"{V3_API_PREFIX}/users/me:change_password", json=json
        )
        assert response.status_code == 204

        # the user we use in tests has the id=0
        services_mock.users.change_password.assert_called_once_with(
            user_id=0, password="foo"
        )

    async def test_change_password_admin(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ) -> None:
        client = mocked_api_client_user_with_permissions(
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
        )
        services_mock.users = Mock(UsersService)
        services_mock.users.change_password.return_value = None

        json = {"password": "foo"}

        response = await client.post(
            f"{V3_API_PREFIX}/users/1:change_password", json=json
        )
        assert response.status_code == 204

        services_mock.users.change_password.assert_called_once_with(
            user_id=1, password="foo"
        )

    async def test_user_statistics(
        self, services_mock: ServiceCollectionV3, mocked_api_client_user
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id_statistics.return_value = UserStatistics(
            id=0,
            completed_intro=True,
            is_local=True,
            machines_count=2,
            sshkeys_count=3,
        )

        response = await mocked_api_client_user.get(
            f"{V3_API_PREFIX}/users/me:statistics"
        )
        assert response.status_code == 200
        user_statistics = UserStatisticsResponse(**response.json())
        assert user_statistics.id == 0
        assert user_statistics.machines_count == 2
        services_mock.users.get_by_id_statistics.assert_called_once_with(id=0)
