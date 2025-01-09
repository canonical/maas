#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import json
from json import dumps as _dumps
from unittest.mock import Mock, patch

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
from macaroonbakery.bakery import Macaroon
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.requests.users import UserRequest
from maasapiserver.v3.api.public.models.responses.users import (
    SshKeysListResponse,
    UserInfoResponse,
    UserResponse,
    UsersListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    DischargeRequiredException,
)
from maasservicelayer.exceptions.constants import (
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.sshkeys import SshKey
from maasservicelayer.models.users import User
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.external_auth import ExternalAuthService
from maasservicelayer.services.sshkeys import SshKeysService
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

SSHKEY_1 = SshKey(id=1, key="ssh-rsa randomkey comment", user_id=1)

SSHKEY_2 = SshKey(
    id=1,
    key="ssh-ed25519 randomkey comment",
    user_id=1,
    protocol=SshKeysProtocolType.LP,
    auth_id="foo",
)


@pytest.mark.asyncio
class TestUsersApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/users"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/me"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
            Endpoint(method="PUT", path=f"{self.BASE_PATH}/1"),
        ]

    # GET /users/me
    async def test_get_user_info(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
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
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/me",
        )
        assert response.status_code == 200

        user_info = UserInfoResponse(**response.json())
        assert user_info.id == 1
        assert user_info.username == "username"
        assert user_info.is_superuser is False

    async def test_get_user_info_admin(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.get_one.return_value = User(
            id=1,
            username="admin",
            password="pass",
            is_superuser=True,
            first_name="",
            last_name="",
            is_staff=True,
            is_active=True,
            date_joined=utcnow(),
            email=None,
            last_login=None,
        )
        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}/me",
        )
        assert response.status_code == 200

        user_info = UserInfoResponse(**response.json())
        assert user_info.id == 1
        assert user_info.username == "admin"
        assert user_info.is_superuser is True

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
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.list.return_value = ListResult[User](
            items=[USER_1], next_token=str(USER_2.id)
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=1",
        )

        assert response.status_code == 200
        users_response = UsersListResponse(**response.json())
        assert len(users_response.items) == 1
        assert (
            users_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(USER_2.id), size='1')}"
        )

    async def test_list_users_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.list.return_value = ListResult[User](
            items=[USER_1, USER_2], next_token=None
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=2",
        )

        assert response.status_code == 200
        users_response = UsersListResponse(**response.json())
        assert len(users_response.items) == 2
        assert users_response.next is None

    # GET /users/{user_id}
    async def test_get_user(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = USER_1
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/1",
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        user_response = UserResponse(**response.json())
        assert user_response.id == 1
        assert user_response.username == "username"

    async def test_get_user_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.get_by_id.return_value = None
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/99",
        )
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_get_user_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.get_one.side_effect = RequestValidationError(
            errors=[]
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/1a",
        )
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    # POST /users/{user_id}
    async def test_post_user(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        create_user_request = UserRequest(
            username="new_username",
            password="new_password",
            is_superuser=False,
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

        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(create_user_request)
        )

        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0

        user_response = UserResponse(**response.json())

        assert user_response.id == new_user.id
        assert user_response.is_superuser == new_user.is_superuser
        assert user_response.username == new_user.username
        assert user_response.password == new_user.password
        assert user_response.first_name == new_user.first_name
        assert user_response.last_name == new_user.last_name
        assert user_response.email == new_user.email
        assert user_response.date_joined == new_user.date_joined

    async def test_post_user_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        create_user_request = UserRequest(
            username="new_username",
            password="new_password",
            is_superuser=False,
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

        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(create_user_request)
        )
        assert response.status_code == 201

        response = await mocked_api_client_admin.post(
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
        mocked_api_client_admin: AsyncClient,
        user_request: dict[str, str],
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.create.return_value = None

        response = await mocked_api_client_admin.post(
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
        mocked_api_client_admin: AsyncClient,
    ) -> None:
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

        user_request = UserRequest(
            is_superuser=True,
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
        )

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/1",
            json=jsonable_encoder(user_request),
        )

        assert response.status_code == 200

        user_response = UserResponse(**response.json())

        assert user_response.id == updated_user.id
        assert user_response.is_superuser == updated_user.is_superuser
        assert user_response.username == updated_user.username
        assert user_response.password == updated_user.password
        assert user_response.first_name == updated_user.first_name
        assert user_response.last_name == updated_user.last_name
        assert user_response.email == updated_user.email

    async def test_put_user_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.update_by_id.return_value = None

        user_request = UserRequest(
            is_superuser=True,
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
        )

        response = await mocked_api_client_admin.put(
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
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.update_by_id.return_value = None

        user_request = UserRequest(
            is_superuser=True,
            username="new_user",
            password="new_pass",
            first_name="new_first_name",
            last_name="new_last_name",
            email="new_email@example.com",
        )

        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/A1",
            json=jsonable_encoder(user_request),
        )

        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 422


class TestSshKeyApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/users/me/sshkeys"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_user_sshkeys_has_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.list.return_value = ListResult[SshKey](
            items=[SSHKEY_1], next_token=str(SSHKEY_2.id)
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=1",
        )

        assert response.status_code == 200
        sshkeys_response = SshKeysListResponse(**response.json())
        assert len(sshkeys_response.items) == 1
        assert (
            sshkeys_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(SSHKEY_2.id), size='1')}"
        )

    async def test_list_user_sshkeys_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.list.return_value = ListResult[SshKey](
            items=[SSHKEY_1, SSHKEY_2]
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=2",
        )

        assert response.status_code == 200
        sshkeys_response = SshKeysListResponse(**response.json())
        assert len(sshkeys_response.items) == 2
        assert sshkeys_response.next is None
