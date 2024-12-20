#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import datetime
from typing import Any
from unittest.mock import Mock

import pytest

from maasservicelayer.auth.jwt import InvalidToken, JWT, UserRole
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.users import UserClauseFactory
from maasservicelayer.exceptions.catalog import UnauthorizedException
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.models.users import User
from maasservicelayer.services import AuthService, SecretsService, UsersService
from maasservicelayer.services.secrets import SecretNotFound


@pytest.fixture(autouse=True)
def prepare():
    # Always reset the AuthService cache
    AuthService.JWT_TOKEN_KEY = None
    yield
    AuthService.JWT_TOKEN_KEY = None


@pytest.mark.asyncio
class TestAuthService:
    def _build_test_user(self, **extra_details: Any) -> User:
        data = {
            "id": 1,
            "username": "myusername",
            "password": "pbkdf2_sha256$260000$f1nMJPH4Z5Wc8QxkTsZ1p6$ylZBpgGE3FNlP2zOU21cYiLtvxwtkglsPKUETtXhzDw=",  # hash('test')
            "is_superuser": False,
            "first_name": "first",
            "last_name": "last",
            "is_staff": False,
            "is_active": True,
            "date_joined": datetime.datetime.now(datetime.timezone.utc),
        }
        data.update(extra_details)
        return User(**data)

    async def test_login(self) -> None:
        user = self._build_test_user()
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = "123"

        users_service_mock = Mock(UsersService)
        users_service_mock.get_one.return_value = user
        auth_service = AuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )
        token = await auth_service.login(user.username, "test")
        assert len(token.encoded) > 0
        assert token.subject == user.username
        assert token.roles == [UserRole.USER]
        users_service_mock.get_one.assert_awaited_once_with(
            QuerySpec(UserClauseFactory.with_username(user.username))
        )

    async def test_login_admin(self) -> None:
        admin = self._build_test_user(is_superuser=True)
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = "123"

        users_service_mock = Mock(UsersService)
        users_service_mock.get_one.return_value = admin
        auth_service = AuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )
        token = await auth_service.login(admin.username, "test")
        assert len(token.encoded) > 0
        assert token.subject == admin.username
        assert set(token.roles) == {UserRole.USER, UserRole.ADMIN}
        users_service_mock.get_one.assert_awaited_once_with(
            QuerySpec(UserClauseFactory.with_username(admin.username))
        )

    async def test_login_unauthorized(self) -> None:
        user = self._build_test_user()
        secrets_service_mock = Mock(SecretsService)
        users_service_mock = Mock(UsersService)
        auth_service = AuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )

        # Username exists but the password is wrong
        users_service_mock.get_one.return_value = user
        with pytest.raises(UnauthorizedException):
            await auth_service.login(user.username, "wrong")

        # Username exists and the password is correct, but the user is disabled
        user.is_active = False
        users_service_mock.get_one.return_value = user
        with pytest.raises(UnauthorizedException):
            await auth_service.login(user.username, "test")

        # Username does not exist
        users_service_mock.get_one.return_value = None
        with pytest.raises(UnauthorizedException):
            await auth_service.login("bb", "test")

    async def test_jwt_key_is_cached(self) -> None:
        user = self._build_test_user()
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = "123"

        users_service_mock = Mock(UsersService)
        users_service_mock.get_one.return_value = user

        auth_service = AuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )
        token = await auth_service.login(user.username, "test")
        assert token.subject == user.username
        assert AuthService.JWT_TOKEN_KEY == "123"
        secrets_service_mock.get_simple_secret.assert_called_once_with(
            AuthService.MAAS_V3_JWT_KEY_SECRET_PATH
        )

        token = await auth_service.login(user.username, "test")
        assert token.subject == user.username
        # The service is not loading anymore the key because it was cached
        secrets_service_mock.get_simple_secret.assert_called_once_with(
            AuthService.MAAS_V3_JWT_KEY_SECRET_PATH
        )

    async def test_jwt_key_is_created(self) -> None:
        user = self._build_test_user()
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.side_effect = SecretNotFound(
            AuthService.MAAS_V3_JWT_KEY_SECRET_PATH
        )
        users_service_mock = Mock(UsersService)
        users_service_mock.get_one.return_value = user

        auth_service = AuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )
        token = await auth_service.login(user.username, "test")
        assert token.subject == user.username
        assert AuthService.JWT_TOKEN_KEY is not None
        secrets_service_mock.get_simple_secret.assert_called_once_with(
            AuthService.MAAS_V3_JWT_KEY_SECRET_PATH
        )
        secrets_service_mock.set_simple_secret.assert_called_once()

    async def test_decode_and_verify_token(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = "123"
        users_service_mock = Mock(UsersService)
        auth_service = AuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )
        jwt = JWT.create("123", "sub", 0, [UserRole.ADMIN])
        decoded_jwt = await auth_service.decode_and_verify_token(jwt.encoded)
        assert jwt.issuer == decoded_jwt.issuer
        assert decoded_jwt.subject == "sub"
        assert decoded_jwt.user_id == 0
        assert decoded_jwt.roles == [UserRole.ADMIN]

    @pytest.mark.parametrize(
        "key, invalid_token",
        [
            ("123", ""),
            # malformed
            ("123", "eyJhbGciOi"),
            # Expired
            (
                "123",
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhYSIsImlzcyI6Ik1BQVMiLCJpYXQiOjE3MDk3MjAzMTUsImV4cCI6MTcwOTcyMDkxNSwiYXVkIjoiYXBpIiwicm9sZXMiOltdfQ.DH7XiHnNokJ1dRJK8IZ0YItqZKihV7qzxfA8Mi0WpfI",
            ),
        ],
    )
    async def test_decode_and_verify_token_invalid(
        self,
        key: str,
        invalid_token: str,
    ) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = key
        users_service_mock = Mock(UsersService)
        auth_service = AuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )
        with pytest.raises(InvalidToken):
            await auth_service.decode_and_verify_token(invalid_token)

    async def test_decode_and_verify_token_signed_with_another_key(
        self,
    ) -> None:
        # signed with another key
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = "123"
        users_service_mock = Mock(UsersService)
        auth_service = AuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )
        token = JWT.create("not_the_same_key", "test", 0, []).encoded
        with pytest.raises(InvalidToken):
            await auth_service.decode_and_verify_token(token)

    async def test_access_token(self) -> None:
        user = self._build_test_user()
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = "123"

        users_service_mock = Mock(UsersService)
        auth_service = AuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )
        authenticated_user = AuthenticatedUser(
            id=user.id, username=user.username, roles={UserRole.USER}
        )
        token = await auth_service.access_token(authenticated_user)
        assert len(token.encoded) > 0
        assert token.subject == user.username
        assert token.roles == [UserRole.USER]

    async def test_access_token_admin(self) -> None:
        admin = self._build_test_user(is_superuser=True)
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = "123"

        users_service_mock = Mock(UsersService)
        auth_service = AuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )
        authenticated_user = AuthenticatedUser(
            id=admin.id,
            username=admin.username,
            roles={UserRole.USER, UserRole.ADMIN},
        )
        token = await auth_service.access_token(authenticated_user)
        assert len(token.encoded) > 0
        assert token.subject == admin.username
        assert set(token.roles) == {UserRole.USER, UserRole.ADMIN}
