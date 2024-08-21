#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
import os
from unittest.mock import AsyncMock, Mock

from macaroonbakery import bakery, checkers
from macaroonbakery.bakery import AuthInfo, DischargeRequiredError
from pymacaroons import Macaroon
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.auth.checker import AsyncAuthChecker, AsyncChecker
from maasapiserver.common.auth.locator import AsyncThirdPartyLocator
from maasapiserver.common.auth.oven import AsyncOven
from maasapiserver.common.models.exceptions import UnauthorizedException
from maasapiserver.common.utils.date import utcnow
from maasapiserver.v3.auth.external_auth import ExternalAuthType
from maasapiserver.v3.db.external_auth import ExternalAuthRepository
from maasapiserver.v3.models.external_auth import RootKey
from maasapiserver.v3.models.users import User
from maasapiserver.v3.services import SecretsService, UsersService
from maasapiserver.v3.services.external_auth import ExternalAuthService
from maasserver.macaroons import _get_macaroon_caveats_ops
from provisioningserver.security import to_bin, to_hex


@pytest.mark.asyncio
class TestExternalAuthService:
    async def test_get_external_auth_candid(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock(
            return_value={
                "key": "mykey",
                "url": "http://10.0.1.23:8081/",
                "user": "admin@candid",
                "domain": "",
                "rbac-url": "",
                "admin-group": "admin",
            }
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        external_auth = await external_auth_service.get_external_auth()
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            path="global/external-auth", default={}
        )
        assert external_auth.url == "http://10.0.1.23:8081"
        assert external_auth.type == ExternalAuthType.CANDID
        assert external_auth.domain == ""
        assert external_auth.admin_group == "admin"

    async def test_get_external_auth_rbac(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock(
            return_value={
                "key": "mykey",
                "url": "",
                "user": "admin@candid",
                "domain": "",
                "rbac-url": "http://10.0.1.23:5000",
                "admin-group": "admin",
            }
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        external_auth = await external_auth_service.get_external_auth()
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            path="global/external-auth", default={}
        )
        assert external_auth.url == "http://10.0.1.23:5000/auth"
        assert external_auth.type == ExternalAuthType.RBAC
        assert external_auth.domain == ""
        assert external_auth.admin_group == ""

    async def test_get_external_auth_not_enabled(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock(return_value={})
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        external_auth = await external_auth_service.get_external_auth()
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            path="global/external-auth", default={}
        )
        assert external_auth is None

    async def test_get_auth_info(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock(
            return_value={
                "key": "SOgnhQ+dcZuCGm03boCauHK4KB3PiK8xi808mq49lpw=",
                "url": "http://10.0.1.23:8081/",
                "user": "admin@candid",
                "domain": "",
                "rbac-url": "",
                "admin-group": "admin",
            }
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        auth_info = await external_auth_service.get_auth_info()
        assert auth_info is not None
        assert auth_info.agents[0].url == "http://10.0.1.23:8081/"
        assert auth_info.agents[0].username == "admin@candid"
        assert auth_info.key == bakery.PrivateKey.deserialize(
            "SOgnhQ+dcZuCGm03boCauHK4KB3PiK8xi808mq49lpw="
        )
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            path="global/external-auth", default=None
        )

    async def test_get_auth_info_not_enabled(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock(
            return_value=None
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        auth_info = await external_auth_service.get_auth_info()
        assert auth_info is None
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            path="global/external-auth", default=None
        )

    async def test_get_or_create_bakery_key(self) -> None:
        key = "SOgnhQ+dcZuCGm03boCauHK4KB3PiK8xi808mq49lpw="
        expected_bakery_key = bakery.PrivateKey.deserialize(key)
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret = AsyncMock(return_value=key)
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        bakery_key = await external_auth_service.get_or_create_bakery_key()

        secrets_service_mock.get_simple_secret.assert_called_once_with(
            path="global/macaroon-key", default=None
        )
        assert expected_bakery_key.key == bakery_key.key
        assert expected_bakery_key.public_key == bakery_key.public_key

    async def test_get_or_create_bakery_key_is_created(self, mocker) -> None:
        fake_private_key = bakery.PrivateKey.deserialize(
            "SOgnhQ+dcZuCGm03boCauHK4KB3PiK8xi808mq49lpw="
        )
        bakery_mock = mocker.patch.object(bakery, "generate_key")
        bakery_mock.return_value = fake_private_key

        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret = AsyncMock(return_value=None)

        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=Mock(ExternalAuthRepository),
        )
        bakery_key = await external_auth_service.get_or_create_bakery_key()

        secrets_service_mock.get_simple_secret.assert_called_once_with(
            path="global/macaroon-key", default=None
        )
        secrets_service_mock.set_simple_secret.assert_called_once_with(
            path="global/macaroon-key",
            value=fake_private_key.serialize().decode("ascii"),
        )
        assert fake_private_key.key == bakery_key.key
        assert fake_private_key.public_key == bakery_key.public_key

    async def get_or_create_bakery_key(self) -> bakery.PrivateKey:
        key = await self.secrets_service.get_simple_secret(
            path=self.BAKERY_KEY_SECRET_PATH, default=None
        )
        if key:
            return bakery.PrivateKey.deserialize(key)

        key = bakery.generate_key()
        await self.secrets_service.set_simple_secret(
            path=self.BAKERY_KEY_SECRET_PATH,
            value=key.serialize().decode("ascii"),
        )
        return key

    async def test_get_rootkey(self) -> None:
        now = utcnow()
        rootkey = RootKey(
            id=1, created=now, updated=now, expiration=now + timedelta(days=1)
        )
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret = AsyncMock(
            return_value="23451aaec7ba1aea923c53b386587a14e650b79520a043d6"
        )
        external_auth_repository_mock = Mock(ExternalAuthRepository)
        external_auth_repository_mock.find_by_id = AsyncMock(
            return_value=rootkey
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=external_auth_repository_mock,
        )
        retrieved_rootkey = await external_auth_service.get(b"1")
        external_auth_repository_mock.find_by_id.assert_called_once_with(id=1)
        secrets_service_mock.get_simple_secret.assert_called_once_with(
            path="rootkey/1/material", default=None
        )
        assert (
            to_bin("23451aaec7ba1aea923c53b386587a14e650b79520a043d6")
            == retrieved_rootkey
        )

    async def test_get_rootkey_not_found(self) -> None:
        external_auth_repository_mock = Mock(ExternalAuthRepository)
        external_auth_repository_mock.find_by_id = AsyncMock(return_value=None)
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=Mock(SecretsService),
            users_service=Mock(UsersService),
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
        secrets_service_mock.delete = AsyncMock(return_value=None)
        external_auth_repository_mock = Mock(ExternalAuthRepository)
        external_auth_repository_mock.find_by_id = AsyncMock(
            return_value=rootkey
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=external_auth_repository_mock,
        )
        retrieved_rootkey = await external_auth_service.get(b"1")
        external_auth_repository_mock.find_by_id.assert_called_once_with(id=1)
        external_auth_repository_mock.delete.assert_called_once_with(id=1)
        secrets_service_mock.delete.assert_called_once_with(
            path="rootkey/1/material"
        )
        assert retrieved_rootkey is None

    async def test_root_key(self) -> None:
        now = utcnow()
        rootkey = RootKey(
            id=1, created=now, updated=now, expiration=now + timedelta(days=1)
        )
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_simple_secret = AsyncMock(
            return_value="23451aaec7ba1aea923c53b386587a14e650b79520a043d6"
        )
        external_auth_repository_mock = Mock(ExternalAuthRepository)
        external_auth_repository_mock.find_best_key = AsyncMock(
            return_value=rootkey
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=external_auth_repository_mock,
        )
        retrieved_rootkey, key_id = await external_auth_service.root_key()
        external_auth_repository_mock.find_best_key.assert_called_once()
        secrets_service_mock.get_simple_secret.assert_called_once_with(
            path="rootkey/1/material", default=None
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
        secrets_service_mock.get_simple_secret = AsyncMock(
            return_value=hex_os_urandom
        )

        external_auth_repository_mock = Mock(ExternalAuthRepository)
        external_auth_repository_mock.find_best_key = AsyncMock(
            return_value=None
        )
        external_auth_repository_mock.find_expired_keys = AsyncMock(
            return_value=[expired_rootkey]
        )
        external_auth_repository_mock.create = AsyncMock(return_value=rootkey)

        os_mock = mocker.patch.object(os, "urandom")
        os_mock.return_value = os_urandom

        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=external_auth_repository_mock,
        )
        retrieved_rootkey, key_id = await external_auth_service.root_key()

        # It looks for the existing best key
        external_auth_repository_mock.find_best_key.assert_called_once()

        # The expired key is deleted
        external_auth_repository_mock.delete.assert_called_once_with(id=1)
        secrets_service_mock.delete.assert_called_once_with(
            path="rootkey/1/material"
        )

        # The new key is created
        secrets_service_mock.set_simple_secret.assert_called_once_with(
            path="rootkey/2/material", value=hex_os_urandom
        )
        secrets_service_mock.get_simple_secret.assert_called_once_with(
            path="rootkey/2/material", default=None
        )
        os_mock.assert_called_once_with(24)

        assert to_bin(hex_os_urandom) == retrieved_rootkey
        assert key_id == b"2"

    async def test_login_external_auth_not_enabled(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock(return_value={})

        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
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
        checker_mock.allow = AsyncMock(
            side_effect=bakery.DischargeRequiredError(None, None, None)
        )

        macaroon_bakery = Mock(bakery.Bakery)
        macaroon_bakery.checker.auth = Mock(return_value=checker_mock)

        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=Mock(SecretsService),
            users_service=Mock(UsersService),
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
        checker_mock.allow = AsyncMock(
            return_value=AuthInfo(
                identity=bakery.SimpleIdentity(user="admin"), macaroons=None
            )
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
        users_service_mock.get = AsyncMock(return_value=fake_user)

        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=Mock(SecretsService),
            users_service=users_service_mock,
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        user = await external_auth_service._login(
            [[Mock(Macaroon)]], macaroon_bakery_mock
        )
        assert user == fake_user
        users_service_mock.get.assert_called_once_with(username="admin")

    async def test_get_bakery_if_external_auth_is_not_configured(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock(return_value={})

        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        bakery_instance = await external_auth_service.get_bakery(
            "http://localhost:5000/"
        )
        assert bakery_instance is None

    async def test_get_bakery(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        # get the external auth config
        secrets_service_mock.get_composite_secret = AsyncMock(
            return_value={
                "key": "mykey",
                "url": "",
                "user": "admin@candid",
                "domain": "",
                "rbac-url": "http://10.0.1.23:5000",
                "admin-group": "admin",
            }
        )

        # get the bakery key
        secrets_service_mock.get_simple_secret = AsyncMock(
            return_value="SOgnhQ+dcZuCGm03boCauHK4KB3PiK8xi808mq49lpw="
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
            external_auth_repository=Mock(ExternalAuthRepository),
        )

        bakery_instance = await external_auth_service.get_bakery(
            "http://localhost:5000/"
        )
        assert bakery_instance is not None
        assert isinstance(bakery_instance.checker, AsyncChecker)
        assert isinstance(bakery_instance.oven, AsyncOven)
        assert bakery_instance.oven.key == bakery.PrivateKey.deserialize(
            "SOgnhQ+dcZuCGm03boCauHK4KB3PiK8xi808mq49lpw="
        )
        assert isinstance(bakery_instance.oven.locator, AsyncThirdPartyLocator)
        assert bakery_instance.oven.locator._allow_insecure is True
        assert bakery_instance.oven.location == "http://localhost:5000/"

    async def test_get_discharge_macaroon(self, mock_aioresponse) -> None:
        secrets_service_mock = Mock(SecretsService)
        # get the external auth config
        secrets_service_mock.get_composite_secret = AsyncMock(
            return_value={
                "key": "mykey",
                "url": "",
                "user": "admin@candid",
                "domain": "",
                "rbac-url": "http://10.0.1.23:5000",
                "admin-group": "admin",
            }
        )

        os_urandom = b"\xf2\x92\x8b\x04G|@\x9fRP\xcb\xd6\x8d\xad\xee\x88A\xa4T\x9d\xe5Rx\xc6o\x1bc\x1e*\xb3\xfe}"
        hex_os_urandom = to_hex(os_urandom)
        bakery_key = "SOgnhQ+dcZuCGm03boCauHK4KB3PiK8xi808mq49lpw="
        # There are 2 subsequent calls to get_simple_secret:
        # - the first one will get the bakery key
        # - the second one will get the material key
        secrets_service_mock.get_simple_secret = AsyncMock(
            side_effect=[bakery_key, hex_os_urandom]
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
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
        secrets_service_mock.get_composite_secret = AsyncMock(
            return_value={
                "key": "mykey",
                "url": "",
                "user": "admin@candid",
                "domain": "",
                "rbac-url": "http://10.0.1.23:5000",
                "admin-group": "admin",
            }
        )

        os_urandom = b"\xf2\x92\x8b\x04G|@\x9fRP\xcb\xd6\x8d\xad\xee\x88A\xa4T\x9d\xe5Rx\xc6o\x1bc\x1e*\xb3\xfe}"
        hex_os_urandom = to_hex(os_urandom)
        bakery_key = "SOgnhQ+dcZuCGm03boCauHK4KB3PiK8xi808mq49lpw="
        # There are 2 subsequent calls to get_simple_secret:
        # - the first one will get the bakery key
        # - the second one will get the material key
        secrets_service_mock.get_simple_secret = AsyncMock(
            side_effect=[bakery_key, hex_os_urandom]
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
            users_service=Mock(UsersService),
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
