# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64
from datetime import timedelta
import os
from unittest.mock import ANY, AsyncMock, call, Mock, patch

from authlib.jose import JWTClaims
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from httpx import AsyncClient, HTTPError, Response
from httpx import Request as HTTPXRequest
from macaroonbakery import bakery, checkers
from macaroonbakery.bakery import AuthInfo, DischargeRequiredError
from pymacaroons import Macaroon
import pytest

from maascommon.logging.security import AUTHN_LOGIN_SUCCESSFUL, SECURITY
from maasserver.macaroons import _get_macaroon_caveats_ops
from maasservicelayer.auth.external_auth import ExternalAuthType
from maasservicelayer.auth.external_oauth import (
    OAuth2Client,
    OAuthAccessToken,
    OAuthCallbackData,
    OAuthIDToken,
    OAuthRefreshData,
    OAuthTokenData,
    OAuthUserData,
)
from maasservicelayer.auth.macaroons.checker import (
    AsyncAuthChecker,
    AsyncChecker,
)
from maasservicelayer.auth.macaroons.locator import AsyncThirdPartyLocator
from maasservicelayer.auth.macaroons.oven import AsyncOven
from maasservicelayer.builders.external_auth import OAuthProviderBuilder
from maasservicelayer.builders.users import UserBuilder, UserProfileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.external_auth import (
    ExternalAuthRepository,
    ExternalOAuthRepository,
)
from maasservicelayer.db.repositories.users import UserClauseFactory
from maasservicelayer.exceptions.catalog import (
    BadGatewayException,
    ConflictException,
    DischargeRequiredException,
    PreconditionFailedException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    CONFLICT_VIOLATION_TYPE,
    INVALID_TOKEN_VIOLATION_TYPE,
    MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
    PRECONDITION_FAILED,
    PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
)
from maasservicelayer.models.external_auth import (
    AccessTokenType,
    OAuthProvider,
    ProviderMetadata,
    RootKey,
)
from maasservicelayer.models.secrets import RootKeyMaterialSecret
from maasservicelayer.models.users import User, UserProfile
from maasservicelayer.services import SecretsService, UsersService
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.external_auth import (
    ExternalAuthService,
    ExternalAuthServiceCache,
    ExternalOAuthService,
    ExternalOAuthServiceCache,
)
from maasservicelayer.services.secrets import SecretNotFound
from maasservicelayer.services.tokens import OIDCRevokedTokenService
from maasservicelayer.utils.date import utcnow
from maasservicelayer.utils.encryptor import Encryptor
from provisioningserver.security import to_bin, to_hex
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_KEY = "SOgnhQ+dcZuCGm03boCauHK4KB3PiK8xi808mq49lpw="

TEST_CONFIG_CANDID = {
    "key": TEST_KEY,
    "url": "http://10.0.1.23:8081/",
    "user": "admin@candid",
    "domain": "",
    "rbac-url": "",
    "admin-group": "admin",
}

TEST_CONFIG_RBAC = {
    "key": TEST_KEY,
    "url": "",
    "user": "admin@candid",
    "domain": "",
    "rbac-url": "http://10.0.1.23:5000",
    "admin-group": "admin",
}


@pytest.mark.asyncio
class TestExternalAuthService:
    async def test_get_external_auth_candid(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret.return_value = (
            TEST_CONFIG_CANDID
        )
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        external_auth = await external_auth_service.get_external_auth()
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            model=external_auth_service.EXTERNAL_AUTH_SECRET, default={}
        )
        assert external_auth.url == "http://10.0.1.23:8081"
        assert external_auth.type == ExternalAuthType.CANDID
        assert external_auth.domain == ""
        assert external_auth.admin_group == "admin"

    async def test_get_external_auth_rbac(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret.return_value = (
            TEST_CONFIG_RBAC
        )
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        external_auth = await external_auth_service.get_external_auth()
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            model=external_auth_service.EXTERNAL_AUTH_SECRET, default={}
        )
        assert external_auth.url == "http://10.0.1.23:5000/auth"
        assert external_auth.type == ExternalAuthType.RBAC
        assert external_auth.domain == ""
        assert external_auth.admin_group == ""

    async def test_get_external_auth_not_enabled(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret.return_value = {}
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        external_auth = await external_auth_service.get_external_auth()
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            model=external_auth_service.EXTERNAL_AUTH_SECRET, default={}
        )
        assert external_auth is None

    async def test_get_auth_info(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret.return_value = (
            TEST_CONFIG_CANDID
        )
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        auth_info = await external_auth_service.get_auth_info()
        assert auth_info is not None
        assert auth_info.agents[0].url == "http://10.0.1.23:8081/"
        assert auth_info.agents[0].username == "admin@candid"
        assert auth_info.key == bakery.PrivateKey.deserialize(TEST_KEY)
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            model=external_auth_service.EXTERNAL_AUTH_SECRET, default=None
        )

    async def test_get_auth_info_not_enabled(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret.return_value = None
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        auth_info = await external_auth_service.get_auth_info()
        assert auth_info is None
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            model=external_auth_service.EXTERNAL_AUTH_SECRET, default=None
        )

    async def test_get_or_create_bakery_key(self) -> None:
        key = TEST_KEY
        expected_bakery_key = bakery.PrivateKey.deserialize(key)
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = key
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        bakery_key = await external_auth_service.get_or_create_bakery_key()

        secrets_service_mock.get_simple_secret.assert_called_once_with(
            model=external_auth_service.BAKERY_KEY_SECRET, default=None
        )
        assert expected_bakery_key.key == bakery_key.key
        assert expected_bakery_key.public_key == bakery_key.public_key

    async def test_get_or_create_bakery_key_is_created(self, mocker) -> None:
        fake_private_key = bakery.PrivateKey.deserialize(TEST_KEY)
        bakery_mock = mocker.patch.object(bakery, "generate_key")
        bakery_mock.return_value = fake_private_key

        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = None

        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        bakery_key = await external_auth_service.get_or_create_bakery_key()

        secrets_service_mock.get_simple_secret.assert_called_once_with(
            model=external_auth_service.BAKERY_KEY_SECRET, default=None
        )
        secrets_service_mock.set_simple_secret.assert_called_once_with(
            model=external_auth_service.BAKERY_KEY_SECRET,
            value=fake_private_key.serialize().decode("ascii"),
        )
        assert fake_private_key.key == bakery_key.key
        assert fake_private_key.public_key == bakery_key.public_key

    async def test_get_rootkey(self) -> None:
        now = utcnow()
        rootkey = RootKey(
            id=1, created=now, updated=now, expiration=now + timedelta(days=1)
        )
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = (
            "23451aaec7ba1aea923c53b386587a14e650b79520a043d6"
        )
        external_auth_repository_mock = Mock(ExternalAuthRepository)
        external_auth_repository_mock.find_by_id.return_value = rootkey
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=external_auth_repository_mock,
        )
        retrieved_rootkey = await external_auth_service.get(b"1")
        external_auth_repository_mock.find_by_id.assert_called_once_with(id=1)
        secrets_service_mock.get_simple_secret.assert_called_once_with(
            model=RootKeyMaterialSecret(id=1), default=None
        )
        assert (
            to_bin("23451aaec7ba1aea923c53b386587a14e650b79520a043d6")
            == retrieved_rootkey
        )

    async def test_get_rootkey_not_found(self) -> None:
        external_auth_repository_mock = Mock(ExternalAuthRepository)
        external_auth_repository_mock.find_by_id.return_value = None
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=Mock(SecretsService),
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=external_auth_repository_mock,
        )
        retrieved_rootkey = await external_auth_service.get(b"1")
        external_auth_repository_mock.find_by_id.assert_called_once_with(id=1)
        assert retrieved_rootkey is None

    async def test_get_rootkey_deletes_expired_key(self) -> None:
        now = utcnow()
        rootkey = RootKey(
            id=1, created=now, updated=now, expiration=now - timedelta(days=1)
        )
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.delete.return_value = None
        external_auth_repository_mock = Mock(ExternalAuthRepository)
        external_auth_repository_mock.find_by_id.return_value = rootkey
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=external_auth_repository_mock,
        )
        retrieved_rootkey = await external_auth_service.get(b"1")
        external_auth_repository_mock.find_by_id.assert_called_once_with(id=1)
        external_auth_repository_mock.delete.assert_called_once_with(id=1)
        secrets_service_mock.delete.assert_called_once_with(
            model=RootKeyMaterialSecret(id=1)
        )
        assert retrieved_rootkey is None

    async def test_root_key(self) -> None:
        now = utcnow()
        rootkey = RootKey(
            id=1, created=now, updated=now, expiration=now + timedelta(days=1)
        )
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = (
            "23451aaec7ba1aea923c53b386587a14e650b79520a043d6"
        )
        external_auth_repository_mock = Mock(ExternalAuthRepository)
        external_auth_repository_mock.find_best_key.return_value = rootkey
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=external_auth_repository_mock,
        )
        retrieved_rootkey, key_id = await external_auth_service.root_key()
        external_auth_repository_mock.find_best_key.assert_called_once()
        secrets_service_mock.get_simple_secret.assert_called_once_with(
            model=RootKeyMaterialSecret(id=1), default=None
        )
        assert (
            to_bin("23451aaec7ba1aea923c53b386587a14e650b79520a043d6")
            == retrieved_rootkey
        )
        assert key_id == b"1"

    async def test_root_key_creates_new_key_deletes_old_keys(
        self, mocker
    ) -> None:
        now = utcnow()
        os_urandom = b"\xf2\x92\x8b\x04G|@\x9fRP\xcb\xd6\x8d\xad\xee\x88A\xa4T\x9d\xe5Rx\xc6o\x1bc\x1e*\xb3\xfe}"
        hex_os_urandom = to_hex(os_urandom)
        expired_rootkey = RootKey(
            id=1, created=now, updated=now, expiration=now - timedelta(days=1)
        )
        rootkey = RootKey(
            id=2, created=now, updated=now, expiration=now + timedelta(days=1)
        )

        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret.return_value = hex_os_urandom

        external_auth_repository_mock = Mock(ExternalAuthRepository)
        external_auth_repository_mock.find_best_key.return_value = None
        external_auth_repository_mock.find_expired_keys.return_value = [
            expired_rootkey
        ]
        external_auth_repository_mock.create.return_value = rootkey

        os_mock = mocker.patch.object(os, "urandom")
        os_mock.return_value = os_urandom

        external_auth_service = ExternalAuthService(
            context=Context(trace_id="1224"),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=external_auth_repository_mock,
        )
        retrieved_rootkey, key_id = await external_auth_service.root_key()

        # It looks for the existing best key
        external_auth_repository_mock.find_best_key.assert_called_once()

        # The expired key is deleted
        external_auth_repository_mock.delete.assert_called_once_with(id=1)
        secrets_service_mock.delete.assert_called_once_with(
            model=RootKeyMaterialSecret(id=1)
        )

        # The new key is created
        secrets_service_mock.set_simple_secret.assert_called_once_with(
            model=RootKeyMaterialSecret(id=2), value=hex_os_urandom
        )
        secrets_service_mock.get_simple_secret.assert_called_once_with(
            model=RootKeyMaterialSecret(id=2), default=None
        )
        os_mock.assert_called_once_with(24)

        assert to_bin(hex_os_urandom) == retrieved_rootkey
        assert key_id == b"2"

    async def test_login_external_auth_not_enabled(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret.return_value = {}

        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        with pytest.raises(UnauthorizedException) as exc:
            await external_auth_service.login(
                [[Mock(Macaroon)]], "http://localhost:5000/"
            )
        assert (
            exc.value.details[0].message
            == "Macaroon based authentication is not enabled on this server."
        )

    async def test_login_external_auth_invalid_macaroon(self) -> None:
        checker_mock = Mock(AsyncAuthChecker)
        checker_mock.allow.side_effect = bakery.DischargeRequiredError(
            None, None, None
        )

        macaroon_bakery = Mock(bakery.Bakery)
        macaroon_bakery.checker.auth = Mock(return_value=checker_mock)

        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=Mock(SecretsService),
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        with pytest.raises(DischargeRequiredError):
            await external_auth_service._login(
                [[Mock(Macaroon)]], macaroon_bakery
            )
        checker_mock.allow.assert_called_once_with(
            ctx=checkers.AuthContext(), ops=[bakery.LOGIN_OP]
        )

    async def test_login_external_auth_is_valid(self) -> None:
        checker_mock = Mock(AsyncAuthChecker)
        checker_mock.allow.return_value = AuthInfo(
            identity=bakery.SimpleIdentity(user="admin"), macaroons=None
        )

        macaroon_bakery_mock = Mock(bakery.Bakery)
        macaroon_bakery_mock.checker.auth = Mock(return_value=checker_mock)

        fake_user = User(
            id=0,
            username="admin",
            password="",
            is_superuser=False,
            first_name="",
            last_name="",
            is_staff=False,
            is_active=True,
            date_joined=utcnow(),
        )

        users_service_mock = Mock(UsersService)
        users_service_mock.get_or_create.return_value = (fake_user, False)

        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=Mock(SecretsService),
            users_service=users_service_mock,
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        user = await external_auth_service._login(
            [[Mock(Macaroon)]], macaroon_bakery_mock
        )
        assert user == fake_user
        users_service_mock.get_or_create.assert_called_once_with(
            query=QuerySpec(UserClauseFactory.with_username("admin")),
            builder=ANY,
        )

    async def test_login_external_auth_user_not_in_db(self) -> None:
        checker_mock = Mock(AsyncAuthChecker)
        checker_mock.allow.return_value = AuthInfo(
            identity=bakery.SimpleIdentity(user="admin"), macaroons=None
        )

        macaroon_bakery_mock = Mock(bakery.Bakery)
        macaroon_bakery_mock.checker.auth = Mock(return_value=checker_mock)

        now = utcnow()

        fake_user = User(
            id=0,
            username="admin",
            password="",
            is_superuser=False,
            first_name="admin",
            is_staff=False,
            is_active=True,
            date_joined=now,
        )

        fake_profile = UserProfile(
            id=0,
            completed_intro=True,
            is_local=False,
            auth_last_check=now,
            user_id=fake_user.id,
        )

        user_builder = UserBuilder(
            username="admin",
            first_name="",
            password="",
            is_active=True,
            is_staff=False,
            is_superuser=False,
            last_login=now,
        )

        profile_builder = UserProfileBuilder(
            is_local=False, completed_intro=True, auth_last_check=now
        )
        users_service_mock = Mock(UsersService)
        users_service_mock.get_or_create.return_value = (fake_user, False)
        users_service_mock.update_profile.return_value = fake_profile

        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=Mock(SecretsService),
            users_service=users_service_mock,
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        with patch(
            "maasservicelayer.services.external_auth.utcnow"
        ) as utcnow_mock:
            utcnow_mock.return_value = now
            user = await external_auth_service._login(
                [[Mock(Macaroon)]], macaroon_bakery_mock
            )
        assert user == fake_user
        users_service_mock.get_or_create.assert_called_once_with(
            query=QuerySpec(
                UserClauseFactory.with_username(fake_user.username)
            ),
            builder=user_builder,
        )
        users_service_mock.update_profile.assert_called_once_with(
            fake_user.id, profile_builder
        )

    async def test_get_bakery_if_external_auth_is_not_configured(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret.return_value = {}

        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        bakery_instance = await external_auth_service.get_bakery(
            "http://localhost:5000/"
        )
        assert bakery_instance is None

    async def test_get_bakery(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        # get the external auth config
        secrets_service_mock.get_composite_secret.return_value = (
            TEST_CONFIG_RBAC
        )
        # get the bakery key
        secrets_service_mock.get_simple_secret.return_value = TEST_KEY
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        bakery_instance = await external_auth_service.get_bakery(
            "http://localhost:5000/"
        )
        assert bakery_instance is not None
        assert isinstance(bakery_instance.checker, AsyncChecker)
        assert isinstance(bakery_instance.oven, AsyncOven)
        assert bakery_instance.oven.key == bakery.PrivateKey.deserialize(
            TEST_KEY
        )
        assert isinstance(bakery_instance.oven.locator, AsyncThirdPartyLocator)
        assert bakery_instance.oven.locator._allow_insecure is True
        assert bakery_instance.oven.location == "http://localhost:5000/"

    async def test_get_discharge_macaroon(self, mock_aioresponse) -> None:
        secrets_service_mock = Mock(SecretsService)
        # get the external auth config
        secrets_service_mock.get_composite_secret.return_value = (
            TEST_CONFIG_RBAC
        )
        os_urandom = b"\xf2\x92\x8b\x04G|@\x9fRP\xcb\xd6\x8d\xad\xee\x88A\xa4T\x9d\xe5Rx\xc6o\x1bc\x1e*\xb3\xfe}"
        hex_os_urandom = to_hex(os_urandom)
        # There are 2 subsequent calls to get_simple_secret:
        # - the first one will get the bakery key
        # - the second one will get the material key
        secrets_service_mock.get_simple_secret.side_effect = [
            TEST_KEY,
            hex_os_urandom,
        ]
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        bakery_instance = await external_auth_service.get_bakery(
            "http://localhost:5000/"
        )

        third_party_key = bakery.generate_key()

        # mock the call to the third party auth
        mock_aioresponse.get(
            "http://10.0.1.23:5000/auth/discharge/info",
            payload={
                "Version": bakery.LATEST_VERSION,
                "PublicKey": str(third_party_key.public_key),
            },
        )

        external_auth_info = await external_auth_service.get_external_auth()

        caveats, ops = _get_macaroon_caveats_ops(
            external_auth_info.url, external_auth_info.domain
        )

        discharge_macaroon = (
            await external_auth_service.generate_discharge_macaroon(
                macaroon_bakery=bakery_instance, caveats=caveats, ops=ops
            )
        )
        macaroon = discharge_macaroon.macaroon
        assert macaroon.location == "http://localhost:5000/"
        assert len(macaroon.first_party_caveats()) == 1
        assert (
            macaroon.third_party_caveats()[0].location
            == "http://10.0.1.23:5000/auth"
        )

    async def test_get_discharge_macaroon_from_error(
        self, mock_aioresponse
    ) -> None:
        secrets_service_mock = Mock(SecretsService)
        # get the external auth config
        secrets_service_mock.get_composite_secret.return_value = (
            TEST_CONFIG_RBAC
        )
        os_urandom = b"\xf2\x92\x8b\x04G|@\x9fRP\xcb\xd6\x8d\xad\xee\x88A\xa4T\x9d\xe5Rx\xc6o\x1bc\x1e*\xb3\xfe}"
        hex_os_urandom = to_hex(os_urandom)
        # There are 2 subsequent calls to get_simple_secret:
        # - the first one will get the bakery key
        # - the second one will get the material key
        secrets_service_mock.get_simple_secret.side_effect = [
            TEST_KEY,
            hex_os_urandom,
        ]
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        bakery_instance = await external_auth_service.get_bakery(
            "http://localhost:5000/"
        )

        third_party_key = bakery.generate_key()

        # mock the call to the third party auth
        mock_aioresponse.get(
            "http://10.0.1.23:5000/auth/discharge/info",
            payload={
                "Version": bakery.LATEST_VERSION,
                "PublicKey": str(third_party_key.public_key),
            },
        )

        # This is how caveats are retrieved when building a DischargeRequiredError
        _, caveats = (
            bakery_instance.checker._identity_client.identity_from_context(
                ctx=None
            )
        )
        ops = [bakery.LOGIN_OP]
        discharge_error = bakery.DischargeRequiredError(
            msg="Discharge required", ops=ops, cavs=caveats
        )

        discharge_macaroon = (
            await external_auth_service.generate_discharge_macaroon(
                macaroon_bakery=bakery_instance,
                caveats=discharge_error.cavs(),
                ops=discharge_error.ops(),
            )
        )
        macaroon = discharge_macaroon.macaroon
        assert macaroon.location == "http://localhost:5000/"
        assert len(macaroon.first_party_caveats()) == 1
        assert (
            macaroon.third_party_caveats()[0].location
            == "http://10.0.1.23:5000/auth"
        )

    async def test_raise_discharge_exception(self, mock_aioresponse):
        secrets_service_mock = Mock(SecretsService)
        # get the external auth config
        secrets_service_mock.get_composite_secret.return_value = (
            TEST_CONFIG_RBAC
        )
        os_urandom = b"\xf2\x92\x8b\x04G|@\x9fRP\xcb\xd6\x8d\xad\xee\x88A\xa4T\x9d\xe5Rx\xc6o\x1bc\x1e*\xb3\xfe}"
        hex_os_urandom = to_hex(os_urandom)
        # There are 2 subsequent calls to get_simple_secret:
        # - the first one will get the bakery key
        # - the second one will get the material key
        secrets_service_mock.get_simple_secret.side_effect = [
            TEST_KEY,
            hex_os_urandom,
        ]
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        third_party_key = bakery.generate_key()
        # mock the call to the third party auth
        mock_aioresponse.get(
            "http://10.0.1.23:5000/auth/discharge/info",
            payload={
                "Version": bakery.LATEST_VERSION,
                "PublicKey": str(third_party_key.public_key),
            },
        )

        external_auth_info = await external_auth_service.get_external_auth()

        with pytest.raises(DischargeRequiredException) as exc_info:
            await external_auth_service.raise_discharge_required_exception(
                external_auth_info, "http://test"
            )
        assert exc_info.value.args[0] == "Macaroon discharge required."

    async def test_cache(self):
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret.return_value = (
            TEST_CONFIG_RBAC
        )
        secrets_service_mock.get_simple_secret.return_value = TEST_KEY
        external_auth_service = ExternalAuthService(
            context=Context(),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            cache=ExternalAuthService.build_cache_object(),
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        assert type(external_auth_service.cache) is ExternalAuthServiceCache
        # external_auth
        ext_auth1 = await external_auth_service.get_external_auth()
        assert external_auth_service.cache.external_auth_config is not None
        ext_auth2 = await external_auth_service.get_external_auth()
        assert (
            ext_auth1
            == ext_auth2
            == external_auth_service.cache.external_auth_config
        )
        # if we hit the cache we call get_composite_secret only once
        secrets_service_mock.get_composite_secret.assert_called_once()
        external_auth_service.cache.clear()
        secrets_service_mock.reset_mock()

        # bakery_key
        bakery_key = await external_auth_service.get_or_create_bakery_key()
        assert external_auth_service.cache.bakery_key is not None
        bakery_key2 = await external_auth_service.get_or_create_bakery_key()
        assert (
            bakery_key == bakery_key2 == external_auth_service.cache.bakery_key
        )
        secrets_service_mock.get_simple_secret.assert_called_once()
        external_auth_service.cache.clear()
        secrets_service_mock.reset_mock()

        # candid_client
        client1 = await external_auth_service.get_candid_client()
        assert external_auth_service.cache.candid_client is not None
        client2 = await external_auth_service.get_candid_client()
        assert client1 == client2 == external_auth_service.cache.candid_client
        secrets_service_mock.get_composite_secret.assert_called_once()
        external_auth_service.cache.clear()
        secrets_service_mock.reset_mock()

        # rbac_client
        client1 = await external_auth_service.get_rbac_client()
        assert external_auth_service.cache.rbac_client is not None
        client2 = await external_auth_service.get_rbac_client()
        assert client1 == client2 == external_auth_service.cache.rbac_client
        # get_rbac_client calls get_auth_info and get_external_auth
        secrets_service_mock.get_composite_secret.assert_has_calls(
            [
                call(
                    model=ExternalAuthService.EXTERNAL_AUTH_SECRET,
                    default=None,
                ),
                call(
                    model=ExternalAuthService.EXTERNAL_AUTH_SECRET,
                    default={},
                ),
            ]
        )
        external_auth_service.cache.clear()


@pytest.mark.asyncio
class TestExternalOAuthService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return ExternalOAuthService(
            context=Context(),
            external_oauth_repository=Mock(ExternalOAuthRepository),
            revoked_tokens_service=Mock(OIDCRevokedTokenService),
            secrets_service=Mock(SecretsService),
            users_service=Mock(UsersService),
            cache=Mock(ExternalOAuthServiceCache),
        )

    @pytest.fixture
    def builder_model(self) -> type[OAuthProviderBuilder]:
        return OAuthProviderBuilder

    @pytest.fixture
    def test_instance(self) -> OAuthProvider:
        return OAuthProvider(
            id=1,
            name="test_provider",
            client_id="test_client_id",
            client_secret="test_secret",
            issuer_url="https://example.com",
            redirect_uri="https://example.com/callback",
            scopes="openid email profile",
            enabled=True,
            created=utcnow(),
            updated=utcnow(),
            token_type=AccessTokenType.JWT,
            metadata=ProviderMetadata(
                authorization_endpoint="https://example.com/auth",
                token_endpoint="https://example.com/token",
                jwks_uri="https://example.com/jwks",
            ),
        )

    async def test_create(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
        builder_model: OAuthProviderBuilder,
    ) -> None:
        metadata_raw = {
            "authorization_endpoint": "https://example.com/auth",
            "token_endpoint": "https://example.com/token",
            "userinfo_endpoint": "https://example.com/userinfo",
            "jwks_uri": "https://example.com/jwks",
            "introspection_endpoint": "",
        }
        provider_metadata = ProviderMetadata(**metadata_raw)
        test_instance.metadata = provider_metadata
        service_instance.repository.create = AsyncMock(
            return_value=test_instance
        )
        service_instance.get_provider = AsyncMock(return_value=None)
        service_instance.get_provider_metadata = AsyncMock(
            return_value=provider_metadata
        )

        builder = OAuthProviderBuilder(
            name=test_instance.name,
            client_id=test_instance.client_id,
            client_secret=test_instance.client_secret,
            issuer_url=test_instance.issuer_url,
            redirect_uri=test_instance.redirect_uri,
            scopes=test_instance.scopes,
            enabled=test_instance.enabled,
            metadata=provider_metadata,
        )

        created_provider = await service_instance.create(builder=builder)

        assert created_provider is not None
        assert created_provider == test_instance
        assert created_provider.metadata == provider_metadata

    async def test_create_conflict(
        self,
        service_instance: ExternalOAuthService,
        builder_model: OAuthProviderBuilder,
        test_instance: OAuthProvider,
    ) -> None:
        builder_model.enabled = True
        service_instance.get_provider = AsyncMock(return_value=test_instance)
        with pytest.raises(ConflictException) as exc_info:
            await service_instance.create(builder=builder_model)
        details = exc_info.value.details
        assert details is not None
        assert (
            details[0].message
            == "An enabled OIDC provider already exists. Please disable it first."
        )
        assert details[0].type == CONFLICT_VIOLATION_TYPE

    async def test_get_provider(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        service_instance.repository.get_provider = AsyncMock(
            return_value=test_instance
        )

        provider = await service_instance.get_provider()

        assert provider is not None
        assert provider.name == "test_provider"

    async def test_get_client_success(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        service_instance.get_provider = AsyncMock(return_value=test_instance)

        client = await service_instance.get_client()

        assert isinstance(client, OAuth2Client)
        assert client.provider.name == test_instance.name
        assert client.provider.client_id == test_instance.client_id

    async def test_get_client_not_found(
        self,
        service_instance: ExternalOAuthService,
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        service_instance.get_provider = AsyncMock(return_value=None)

        with pytest.raises(ConflictException) as exc_info:
            await service_instance.get_client()
        details = exc_info.value.details
        assert details is not None
        assert (
            details[0].message
            == "No enabled OIDC provider is configured. Configure and enable an OIDC provider before using OAuth operations."
        )
        assert details[0].type == MISSING_PROVIDER_CONFIG_VIOLATION_TYPE

    async def test_update_provider_success(
        self,
        builder_model: OAuthProviderBuilder,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        service_instance.get_provider = AsyncMock(return_value=test_instance)
        test_instance.client_id = "updated_id"
        test_instance.enabled = False
        service_instance.update_by_id = AsyncMock(return_value=test_instance)
        service_instance.get_provider_metadata = AsyncMock(
            return_value=test_instance.metadata
        )
        builder_model.issuer_url = test_instance.issuer_url

        updated_provider = await service_instance.update_provider(
            id=1, builder=builder_model
        )

        assert updated_provider is not None
        assert updated_provider.client_id == "updated_id"
        assert updated_provider.metadata == test_instance.metadata
        service_instance.get_provider_metadata.assert_awaited_once_with(
            builder_model
        )
        assert not updated_provider.enabled

    async def test_update_provider_enables_when_none_enabled(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
        builder_model: OAuthProviderBuilder,
    ) -> None:
        service_instance.get_provider = AsyncMock(return_value=None)
        service_instance.update_by_id = AsyncMock(return_value=test_instance)
        builder_model.enabled = True
        builder_model.issuer_url = test_instance.issuer_url
        service_instance.get_provider_metadata = AsyncMock(
            return_value=test_instance.metadata
        )
        updated_provider = await service_instance.update_provider(
            id=1, builder=builder_model
        )

        service_instance.update_by_id.assert_awaited_once_with(
            id=1, builder=builder_model
        )
        service_instance.get_provider_metadata.assert_awaited_once_with(
            builder_model
        )
        assert updated_provider == test_instance

    async def test_update_provider_conflict(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
        builder_model: OAuthProviderBuilder,
    ) -> None:
        service_instance.get_provider = AsyncMock(return_value=test_instance)
        builder_model.enabled = True
        builder_model.name = "A new name"

        with pytest.raises(ConflictException) as exc_info:
            await service_instance.update_provider(id=2, builder=builder_model)
        details = exc_info.value.details
        assert details is not None
        assert (
            details[0].message
            == "An enabled OIDC provider already exists. Please disable it first."
        )
        assert details[0].type == CONFLICT_VIOLATION_TYPE

    async def test_delete_by_id(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ):
        test_instance.enabled = False
        return await super().test_delete_by_id(service_instance, test_instance)

    async def test_delete_by_id_precondition_failed(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ):
        with pytest.raises(PreconditionFailedException) as exc_info:
            await super().test_delete_by_id(service_instance, test_instance)
        details = exc_info.value.details
        assert details is not None
        assert (
            details[0].message
            == "This OIDC provider is enabled. Please disable it first."
        )
        assert details[0].type == PRECONDITION_FAILED

    async def test_delete_one(self, service_instance, test_instance):
        test_instance.enabled = False
        return await super().test_delete_one(service_instance, test_instance)

    async def test_delete_one_etag_match(
        self, service_instance, test_instance
    ):
        test_instance.enabled = False
        return await super().test_delete_one_etag_match(
            service_instance, test_instance
        )

    async def test_delete_by_id_etag_match(
        self, service_instance, test_instance
    ):
        test_instance.enabled = False
        return await super().test_delete_by_id_etag_match(
            service_instance, test_instance
        )

    async def test_get_encryptor(self, service_instance: ExternalOAuthService):
        service_instance._get_or_create_cached_encryption_key = AsyncMock(
            return_value=b"0" * 32
        )
        encryptor = await service_instance.get_encryptor()

        assert isinstance(encryptor, Encryptor)

    async def test__get_or_create_cached_encryption_key_cached(
        self, service_instance: ExternalOAuthService
    ):
        key = b"0" * 32
        service_instance.ENCRYPTION_SECRET_KEY = key

        received_key = (
            await service_instance._get_or_create_cached_encryption_key()
        )

        assert received_key == key

    async def test__get_or_create_cached_encryption_key_get(
        self, service_instance: ExternalOAuthService
    ):
        key_bytes = AESGCM.generate_key(128)
        key_b64 = base64.b64encode(key_bytes).decode("utf-8")
        service_instance.ENCRYPTION_SECRET_KEY = None

        service_instance.secrets_service.get_simple_secret = AsyncMock(
            return_value=key_b64
        )
        received_key = (
            await service_instance._get_or_create_cached_encryption_key()
        )

        assert received_key == key_bytes
        assert service_instance.ENCRYPTION_SECRET_KEY == key_bytes

    async def test__get_or_create_cached_encryption_key_create(
        self, service_instance: ExternalOAuthService
    ):
        service_instance.ENCRYPTION_SECRET_KEY = None
        service_instance.secrets_service.get_simple_secret = AsyncMock(
            side_effect=SecretNotFound("/")
        )
        service_instance.secrets_service.set_simple_secret = AsyncMock()

        key = await service_instance._get_or_create_cached_encryption_key()

        assert key is not None
        assert service_instance.ENCRYPTION_SECRET_KEY is not None
        assert isinstance(key, bytes)
        assert isinstance(service_instance.ENCRYPTION_SECRET_KEY, bytes)

    async def test_get_provider_metadata_success(
        self,
        service_instance: ExternalOAuthService,
    ) -> None:
        metadata_raw = {
            "authorization_endpoint": "https://issuer.example.com/auth",
            "token_endpoint": "https://issuer.example.com/token",
            "jwks_uri": "https://issuer.example.com/jwks",
        }
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value=Response(status_code=200, json=metadata_raw)
        )
        service_instance.get_httpx_client = AsyncMock(return_value=mock_client)

        expected_metadata = ProviderMetadata(**metadata_raw)
        builder = OAuthProviderBuilder(
            name="provider_name",
            client_id="client123",
            client_secret="secret123",
            issuer_url="https://issuer.example.com",
            redirect_uri="https://example.com/callback",
            scopes="openid email profile",
            enabled=True,
            metadata=expected_metadata,
        )

        received_metadata = await service_instance.get_provider_metadata(
            builder
        )
        assert received_metadata == expected_metadata
        service_instance.get_httpx_client.assert_awaited_once()

    async def test_get_provider_metadata_failure(
        self,
        service_instance: ExternalOAuthService,
    ) -> None:
        metadata_raw = {
            "authorization_endpoint": "https://issuer.example.com/auth",
            "token_endpoint": "https://issuer.example.com/token",
            "jwks_uri": "https://issuer.example.com/jwks",
        }
        mock_response = Response(
            status_code=500,
            request=HTTPXRequest(
                "GET",
                "https://issuer.example.com/.well-known/openid-configuration",
            ),
        )
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        service_instance.get_httpx_client = AsyncMock(return_value=mock_client)

        expected_metadata = ProviderMetadata(**metadata_raw)
        builder = OAuthProviderBuilder(
            name="provider_name",
            client_id="client123",
            client_secret="secret123",
            issuer_url="https://issuer.example.com",
            redirect_uri="https://example.com/callback",
            scopes="openid email profile",
            enabled=True,
            metadata=expected_metadata,
        )

        with pytest.raises(BadGatewayException) as exc_info:
            await service_instance.get_provider_metadata(builder)
        assert (
            exc_info.value.details[0].message  # type: ignore
            == "OIDC server returned an unexpected response with status code: 500."
        )
        assert (
            exc_info.value.details[0].type  # type: ignore
            == PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE
        )

        mock_client.get = AsyncMock(side_effect=HTTPError("Connection error"))
        service_instance.get_httpx_client = AsyncMock(return_value=mock_client)

        with pytest.raises(BadGatewayException) as exc_info:
            await service_instance.get_provider_metadata(builder)
        assert (
            exc_info.value.details[0].message  # type: ignore
            == "A network error occurred while trying to reach the OIDC server."
        )
        assert (
            exc_info.value.details[0].type  # type: ignore
            == PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE
        )

    async def test_get_httpx_client(
        self, service_instance: ExternalOAuthService
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        client = await service_instance.get_httpx_client()
        assert isinstance(client, AsyncClient)

    async def test_get_httpx_client_cached(
        self, service_instance: ExternalOAuthService
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        client1 = await service_instance.get_httpx_client()
        client2 = await service_instance.get_httpx_client()
        assert client1 is client2

    @patch("maasservicelayer.services.external_auth.logger")
    async def test_get_callback_user_exists(
        self,
        mock_logger: Mock,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        mock_client = AsyncMock()
        now = utcnow()
        mock_client.callback = AsyncMock(
            return_value=OAuthCallbackData(
                tokens=OAuthTokenData(
                    refresh_token="refresh_token_value",
                    access_token=OAuthAccessToken(
                        encoded="access_token_value",
                        provider=test_instance,
                        claims=Mock(),
                    ),
                    id_token=OAuthIDToken(
                        encoded="id_token_value",
                        provider=test_instance,
                        claims=Mock(),
                    ),
                ),
                user_info=OAuthUserData(
                    sub="user123",
                    email="user@example.com",
                    given_name="Test",
                    family_name="User",
                    name="Test User",
                ),
            )
        )
        service_instance.get_client = AsyncMock(return_value=mock_client)
        service_instance.users_service.get_or_create = AsyncMock(
            return_value=(
                User(
                    id=1,
                    username="testuser",
                    password="",
                    is_superuser=False,
                    first_name="Test",
                    last_name="User",
                    is_staff=False,
                    is_active=True,
                    last_login=now,
                    date_joined=now,
                ),
                False,
            )
        )
        service_instance.users_service.update_profile = AsyncMock()

        with patch(
            "maasservicelayer.services.external_auth.utcnow"
        ) as utcnow_mock:
            utcnow_mock.return_value = now
            data = await service_instance.get_callback(
                code="auth_code", nonce="nonce_value"
            )

        service_instance.get_client.assert_awaited_once()
        mock_client.callback.assert_awaited_once_with(
            code="auth_code", nonce="nonce_value"
        )
        service_instance.users_service.get_or_create.assert_awaited_once_with(
            query=QuerySpec(
                UserClauseFactory.with_username_or_email_like(
                    "user@example.com"
                )
            ),
            builder=UserBuilder(
                username="user@example.com",
                email="user@example.com",
                first_name="Test",
                last_name="User",
                password="",
                is_active=True,
                is_staff=False,
                is_superuser=False,
                last_login=now,
                date_joined=now,
            ),
        )
        service_instance.users_service.update_profile.assert_not_called()
        assert isinstance(data, OAuthTokenData)
        assert data.id_token.encoded == "id_token_value"
        assert data.access_token.encoded == "access_token_value"  # type: ignore
        assert data.refresh_token == "refresh_token_value"
        mock_logger.info.assert_called_with(
            AUTHN_LOGIN_SUCCESSFUL,
            type=SECURITY,
            userID="testuser",
            role="User",
        )

    @patch("maasservicelayer.services.external_auth.logger")
    async def test_get_callback_newly_created_user(
        self,
        mock_logger: Mock,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        now = utcnow()
        service_instance.cache = service_instance.build_cache_object()
        mock_client = AsyncMock()
        mock_client.callback = AsyncMock(
            return_value=OAuthCallbackData(
                tokens=OAuthTokenData(
                    refresh_token="refresh_token_value",
                    access_token=OAuthAccessToken(
                        encoded="access_token_value",
                        provider=test_instance,
                        claims=Mock(),
                    ),
                    id_token=OAuthIDToken(
                        encoded="id_token_value",
                        provider=test_instance,
                        claims=Mock(),
                    ),
                ),
                user_info=OAuthUserData(
                    sub="user123",
                    email="user@example.com",
                    given_name="Test",
                    family_name="User",
                    name="Test User",
                ),
            )
        )
        service_instance.get_client = AsyncMock(return_value=mock_client)
        service_instance.users_service.get_or_create = AsyncMock(
            return_value=(
                User(
                    id=1,
                    username="testuser",
                    password="",
                    is_superuser=False,
                    first_name="Test",
                    last_name="User",
                    is_staff=False,
                    is_active=True,
                    last_login=now,
                    date_joined=now,
                ),
                True,
            )
        )
        service_instance.users_service.update_profile = AsyncMock()
        with patch(
            "maasservicelayer.services.external_auth.utcnow"
        ) as utcnow_mock:
            utcnow_mock.return_value = now

            data = await service_instance.get_callback(
                code="auth_code", nonce="nonce_value"
            )

        service_instance.get_client.assert_awaited_once()
        mock_client.callback.assert_awaited_once_with(
            code="auth_code", nonce="nonce_value"
        )
        service_instance.users_service.get_or_create.assert_awaited_once_with(
            query=QuerySpec(
                UserClauseFactory.with_username_or_email_like(
                    "user@example.com"
                )
            ),
            builder=UserBuilder(
                username="user@example.com",
                email="user@example.com",
                first_name="Test",
                last_name="User",
                password="",
                is_active=True,
                is_staff=False,
                is_superuser=False,
                last_login=now,
                date_joined=now,
            ),
        )
        service_instance.users_service.update_profile.assert_awaited_once_with(
            user_id=1,
            builder=UserProfileBuilder(
                is_local=False,
                provider_id=test_instance.id,
            ),
        )
        assert isinstance(data, OAuthTokenData)
        assert data.id_token.encoded == "id_token_value"
        assert data.access_token.encoded == "access_token_value"  # type: ignore
        assert data.refresh_token == "refresh_token_value"
        mock_logger.info.assert_called_with(
            AUTHN_LOGIN_SUCCESSFUL,
            type=SECURITY,
            userID="testuser",
            role="User",
        )

    async def test_revoke_token(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        mock_client = OAuth2Client(provider=test_instance)
        mock_client.parse_raw_id_token = AsyncMock(
            return_value=OAuthIDToken(
                claims=JWTClaims(
                    header=Mock(), payload={"email": "test@example.com"}
                ),
                encoded="id123",
                provider=test_instance,
            )
        )
        mock_client.revoke_token = AsyncMock(return_value=None)
        service_instance.get_client = AsyncMock(return_value=mock_client)
        service_instance.revoked_tokens_service.create_revoked_token = (
            AsyncMock()
        )

        await service_instance.revoke_token(
            id_token="id123", refresh_token="abc123"
        )

        mock_client.parse_raw_id_token.assert_awaited_once_with(
            id_token="id123"
        )
        service_instance.revoked_tokens_service.create_revoked_token.assert_awaited_once_with(
            token="abc123",
            provider_id=1,
            email="test@example.com",
        )
        mock_client.revoke_token.assert_awaited_once_with(token="abc123")

    async def test_validate_access_token(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        mock_client = OAuth2Client(provider=test_instance)
        mock_client.validate_access_token = AsyncMock(
            side_effect=UnauthorizedException()
        )
        service_instance.get_client = AsyncMock(return_value=mock_client)

        with pytest.raises(UnauthorizedException) as exc_info:
            await service_instance.validate_access_token(
                access_token="invalid_token"
            )
            mock_client.validate_access_token.assert_awaited_once_with(
                access_token="invalid_token"
            )
        details = exc_info.value.details
        assert details is not None
        assert details[0].message == "The provided access token is invalid."
        assert details[0].type == INVALID_TOKEN_VIOLATION_TYPE

    async def test_refresh_access_token_success(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        mock_client = OAuth2Client(provider=test_instance)
        mock_client.refresh_access_token = AsyncMock(
            return_value=OAuthRefreshData(
                access_token="new_access_token",
                refresh_token="new_refresh_token",
            )
        )
        service_instance.get_client = AsyncMock(return_value=mock_client)

        tokens = await service_instance.refresh_access_token(
            refresh_token="valid_refresh_token"
        )

        mock_client.refresh_access_token.assert_awaited_once_with(
            refresh_token="valid_refresh_token"
        )
        assert isinstance(tokens, OAuthRefreshData)
        assert tokens.access_token == "new_access_token"
        assert tokens.refresh_token == "new_refresh_token"

    async def test_refresh_access_token_failure(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        mock_client = OAuth2Client(provider=test_instance)
        mock_client.refresh_access_token = AsyncMock(
            side_effect=UnauthorizedException()
        )
        service_instance.get_client = AsyncMock(return_value=mock_client)

        with pytest.raises(UnauthorizedException) as exc_info:
            await service_instance.refresh_access_token(
                refresh_token="invalid_refresh_token"
            )
            mock_client.refresh_access_token.assert_awaited_once_with(
                refresh_token="invalid_refresh_token"
            )
        details = exc_info.value.details
        assert details is not None
        assert details[0].message == "The provided refresh token is invalid."
        assert details[0].type == INVALID_TOKEN_VIOLATION_TYPE

    async def test_get_user_from_id_token_success(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        mock_client = AsyncMock()
        mock_client.parse_raw_id_token = AsyncMock(
            return_value=OAuthIDToken(
                claims=JWTClaims(
                    header=Mock(),
                    payload={
                        "email": "user@example.com",
                        "given_name": "John",
                        "family_name": "Doe",
                    },
                ),
                encoded="id_token_value",
                provider=test_instance,
            )
        )
        service_instance.get_client = AsyncMock(return_value=mock_client)
        mock_user = User(
            id=1,
            username="user@example.com",
            email="user@example.com",
            password="",
            is_superuser=False,
            first_name="John",
            last_name="Doe",
            is_staff=False,
            is_active=True,
            last_login=utcnow(),
            date_joined=utcnow(),
        )
        service_instance.users_service.get_by_username = AsyncMock(
            return_value=mock_user
        )

        user = await service_instance.get_user_from_id_token(
            id_token="valid_id_token"
        )
        mock_client.parse_raw_id_token.assert_awaited_once_with(
            id_token="valid_id_token"
        )
        service_instance.users_service.get_by_username.assert_awaited_once_with(
            username="user@example.com"
        )
        assert user == mock_user

    async def test_get_user_from_id_token_failure(
        self,
        service_instance: ExternalOAuthService,
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        mock_client = AsyncMock()
        mock_client.parse_raw_id_token = AsyncMock(
            side_effect=UnauthorizedException()
        )
        service_instance.get_client = AsyncMock(return_value=mock_client)

        with pytest.raises(UnauthorizedException) as exc_info:
            await service_instance.get_user_from_id_token(
                id_token="invalid_id_token"
            )
        details = exc_info.value.details
        assert details is not None
        assert details[0].message == "Failed to parse ID token."
        assert details[0].type == INVALID_TOKEN_VIOLATION_TYPE
