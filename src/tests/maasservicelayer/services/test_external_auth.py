# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64
from unittest.mock import AsyncMock, Mock, patch

from authlib.jose import JWTClaims
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from httpx import AsyncClient, HTTPError, Response
from httpx import Request as HTTPXRequest
import pytest

from maascommon.logging.security import (
    AUTHN_LOGIN_SUCCESSFUL,
    AUTHN_TOKEN_REVOKED,
    hash_token_for_logging,
    REFRESH_TOKEN,
    SECURITY,
)
from maasservicelayer.auth.external_oauth import (
    OAuth2Client,
    OAuthAccessToken,
    OAuthCallbackData,
    OAuthIDToken,
    OAuthRefreshData,
    OAuthTokenData,
    OAuthUserData,
)
from maasservicelayer.builders.external_auth import OAuthProviderBuilder
from maasservicelayer.builders.users import UserBuilder, UserProfileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.external_auth import (
    ExternalOAuthRepository,
)
from maasservicelayer.db.repositories.users import UserClauseFactory
from maasservicelayer.exceptions.catalog import (
    BadGatewayException,
    ConflictException,
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
    ProviderVendorType,
)
from maasservicelayer.models.users import User, UserProfile
from maasservicelayer.services import SecretsService, UsersService
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.external_auth import (
    ExternalOAuthService,
    ExternalOAuthServiceCache,
)
from maasservicelayer.services.secrets import SecretNotFound
from maasservicelayer.services.tokens import OIDCRevokedTokenService
from maasservicelayer.utils.date import utcnow
from maasservicelayer.utils.encryptor import Encryptor
from tests.maasservicelayer.services.base import ServiceCommonTests


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
            vendor=ProviderVendorType.GENERIC,
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
        builder_model: type[OAuthProviderBuilder],
        test_instance: OAuthProvider,
    ) -> None:
        builder = builder_model()
        builder.enabled = True
        service_instance.get_provider = AsyncMock(return_value=test_instance)
        with pytest.raises(ConflictException) as exc_info:
            await service_instance.create(builder=builder)
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
        builder_model: type[OAuthProviderBuilder],
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
        builder = builder_model()
        builder.issuer_url = test_instance.issuer_url

        updated_provider = await service_instance.update_provider(
            id=1, builder=builder
        )

        assert updated_provider is not None
        assert updated_provider.client_id == "updated_id"
        assert updated_provider.metadata == test_instance.metadata
        service_instance.get_provider_metadata.assert_awaited_once_with(
            builder
        )
        assert not updated_provider.enabled

    async def test_update_provider_enables_when_none_enabled(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
        builder_model: type[OAuthProviderBuilder],
    ) -> None:
        service_instance.get_provider = AsyncMock(return_value=None)
        service_instance.update_by_id = AsyncMock(return_value=test_instance)
        builder = builder_model()
        builder.enabled = True
        builder.issuer_url = test_instance.issuer_url
        service_instance.get_provider_metadata = AsyncMock(
            return_value=test_instance.metadata
        )
        updated_provider = await service_instance.update_provider(
            id=1, builder=builder
        )

        service_instance.update_by_id.assert_awaited_once_with(
            id=1, builder=builder
        )
        service_instance.get_provider_metadata.assert_awaited_once_with(
            builder
        )
        assert updated_provider == test_instance

    async def test_update_provider_conflict(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
        builder_model: type[OAuthProviderBuilder],
    ) -> None:
        service_instance.get_provider = AsyncMock(return_value=test_instance)
        builder = builder_model()
        builder.enabled = True
        builder.name = "A new name"

        with pytest.raises(ConflictException) as exc_info:
            await service_instance.update_provider(id=2, builder=builder)
        details = exc_info.value.details
        assert details is not None
        assert (
            details[0].message
            == "An enabled OIDC provider already exists. Please disable it first."
        )
        assert details[0].type == CONFLICT_VIOLATION_TYPE

    async def test_update_connected_users_active_status(
        self,
        service_instance: ExternalOAuthService,
    ) -> None:
        await service_instance._update_connected_users_active_status(1, True)
        service_instance.users_service.update_many.assert_awaited_once_with(
            query=QuerySpec(where=UserClauseFactory.with_provider_id(1)),
            builder=UserBuilder(is_active=True),
        )

    @pytest.mark.parametrize(
        "enabled_pre,enabled_post,must_update,is_active",
        [
            pytest.param(
                True, False, True, False, id="disabling an enabled provider"
            ),
            pytest.param(
                False, True, True, True, id="enabling a disabled provider"
            ),
            pytest.param(
                True, True, False, None, id="no changes in enabled provider"
            ),
            pytest.param(
                False, False, False, None, id="no changes in disabled provider"
            ),
        ],
    )
    async def test_post_update_hook_update_users(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
        enabled_pre: bool,
        enabled_post: bool,
        must_update: bool,
        is_active: bool | None,
    ) -> None:
        old_resource = test_instance.model_copy()
        old_resource.enabled = enabled_pre
        updated_resource = test_instance.model_copy()
        updated_resource.enabled = enabled_post

        service_instance._update_connected_users_active_status = AsyncMock()

        await service_instance.post_update_hook(old_resource, updated_resource)

        if must_update:
            service_instance._update_connected_users_active_status.assert_awaited_once_with(
                test_instance.id, is_active
            )
        else:
            service_instance._update_connected_users_active_status.assert_not_awaited()

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
        service_instance.get_httpx_client = Mock(return_value=mock_client)

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
        service_instance.get_httpx_client.assert_called_once()

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
        service_instance.get_httpx_client = Mock(return_value=mock_client)

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
        service_instance.get_httpx_client = Mock(return_value=mock_client)

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
        client = service_instance.get_httpx_client()
        assert isinstance(client, AsyncClient)

    async def test_get_httpx_client_cached(
        self, service_instance: ExternalOAuthService
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        client1 = service_instance.get_httpx_client()
        client2 = service_instance.get_httpx_client()
        assert client1 is client2

    async def test_is_active_oidc_user_no_provider(
        self,
        service_instance: ExternalOAuthService,
    ) -> None:
        service_instance.get_provider = AsyncMock(return_value=None)

        assert (
            await service_instance.is_active_oidc_user("user@example.com")
            is False
        )

    @patch("maasservicelayer.services.external_auth.get_provider_adapter")
    async def test_is_active_oidc_user_queries_adapter(
        self,
        mock_get_provider_adapter: Mock,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        test_instance.vendor = ProviderVendorType.ENTRAID
        service_instance.get_provider = AsyncMock(return_value=test_instance)
        service_instance.users_service.get_user_profile = AsyncMock(
            return_value=UserProfile(
                id=1,
                completed_intro=True,
                is_local=False,
                user_id=1,
                provider_id=test_instance.id,
            )
        )
        httpx_client = Mock()
        service_instance.get_httpx_client = Mock(return_value=httpx_client)
        adapter = Mock()
        adapter.user_is_active = AsyncMock(return_value=False)
        mock_get_provider_adapter.return_value = adapter

        result = await service_instance.is_active_oidc_user("user@example.com")

        assert result is False
        mock_get_provider_adapter.assert_called_once_with(
            provider=test_instance, http_client=httpx_client
        )
        adapter.user_is_active.assert_awaited_once_with("user@example.com")

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
            user_id="testuser",
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
            user_id="testuser",
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

    async def test_revoke_token_logging(
        self,
        service_instance: ExternalOAuthService,
        test_instance: OAuthProvider,
    ) -> None:
        """Test that OIDC token revocation is logged."""
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

        with patch(
            "maasservicelayer.services.external_auth.logger"
        ) as mock_logger:
            await service_instance.revoke_token(
                id_token="id123", refresh_token="abc123"
            )

        mock_logger.info.assert_called_once_with(
            f"{AUTHN_TOKEN_REVOKED}:OIDC:{REFRESH_TOKEN}",
            type=SECURITY,
            token_hash=hash_token_for_logging("abc123"),
        )

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
        service_instance.revoked_tokens_service.is_revoked = AsyncMock(
            return_value=False
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
        service_instance.revoked_tokens_service.is_revoked = AsyncMock(
            return_value=False
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

    async def test_refresh_access_token_revoked(
        self,
        service_instance: ExternalOAuthService,
    ) -> None:
        service_instance.cache = service_instance.build_cache_object()
        service_instance.revoked_tokens_service.is_revoked = AsyncMock(
            return_value=True
        )

        with pytest.raises(UnauthorizedException) as exc_info:
            await service_instance.refresh_access_token(
                refresh_token="invalid_refresh_token"
            )

        service_instance.revoked_tokens_service.is_revoked.assert_awaited_once_with(
            "invalid_refresh_token"
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
