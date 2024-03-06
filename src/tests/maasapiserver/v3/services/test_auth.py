import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.models.exceptions import UnauthorizedException
from maasapiserver.v3.models.users import User
from maasapiserver.v3.services import AuthService, SecretsService, UsersService
from maasapiserver.v3.services.secrets import SecretNotFound


@pytest.fixture(autouse=True)
def prepare():
    # Always reset the AuthService cache
    AuthService.JWT_TOKEN_KEY = None
    yield
    AuthService.JWT_TOKEN_KEY = None


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestAuthService:
    def _build_test_user(self) -> User:
        return User(
            id=1,
            username="myusername",
            password="pbkdf2_sha256$260000$f1nMJPH4Z5Wc8QxkTsZ1p6$ylZBpgGE3FNlP2zOU21cYiLtvxwtkglsPKUETtXhzDw=",  # hash('test')
            is_superuser=False,
            first_name="first",
            last_name="last",
            is_staff=False,
            is_active=True,
            date_joined=datetime.datetime.utcnow(),
        )

    async def test_login(self, db_connection: AsyncConnection) -> None:
        user = self._build_test_user()
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret = AsyncMock(return_value="123")

        users_service_mock = Mock(UsersService)
        users_service_mock.get = AsyncMock(return_value=user)
        auth_service = AuthService(
            db_connection,
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )
        token = await auth_service.login(user.username, "test")
        print(token.encoded)
        assert len(token.encoded) > 0
        assert token.subject == user.username

    async def test_login_unauthorized(
        self, db_connection: AsyncConnection
    ) -> None:
        user = self._build_test_user()
        secrets_service_mock = Mock(SecretsService)
        users_service_mock = Mock(UsersService)
        auth_service = AuthService(
            db_connection,
            secrets_service=secrets_service_mock,
            users_service=users_service_mock,
        )

        # Username exists but the password is wrong
        users_service_mock.get = AsyncMock(return_value=user)
        with pytest.raises(UnauthorizedException):
            await auth_service.login(user.username, "wrong")

        # Username exists and the password is correct, but the user is disabled
        user.is_active = False
        users_service_mock.get = AsyncMock(return_value=user)
        with pytest.raises(UnauthorizedException):
            await auth_service.login(user.username, "test")

        # Username does not exist
        users_service_mock.get = AsyncMock(return_value=None)
        with pytest.raises(UnauthorizedException):
            await auth_service.login("bb", "test")

    async def test_jwt_key_is_cached(self, db_connection: AsyncConnection):
        user = self._build_test_user()
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret = AsyncMock(return_value="123")

        users_service_mock = Mock(UsersService)
        users_service_mock.get = AsyncMock(return_value=user)

        auth_service = AuthService(
            db_connection,
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

    async def test_jwt_key_is_created(self, db_connection: AsyncConnection):
        user = self._build_test_user()
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret = AsyncMock(
            side_effect=SecretNotFound(AuthService.MAAS_V3_JWT_KEY_SECRET_PATH)
        )
        secrets_service_mock.set_simple_secret = AsyncMock()

        users_service_mock = Mock(UsersService)
        users_service_mock.get = AsyncMock(return_value=user)

        auth_service = AuthService(
            db_connection,
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
