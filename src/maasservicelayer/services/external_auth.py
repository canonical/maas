# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from httpx import AsyncClient
import structlog

from maascommon.logging.security import (
    ADMIN,
    AUTHN_LOGIN_SUCCESSFUL,
    AUTHN_TOKEN_REVOKED,
    hash_token_for_logging,
    REFRESH_TOKEN,
    SECURITY,
    USER,
)
from maasservicelayer.auth.external_oauth import (
    OAuth2Client,
    OAuthRefreshData,
    OAuthTokenData,
)
from maasservicelayer.auth.oidc_adapters import (
    BaseProviderAdapter,
    get_provider_adapter,
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
    BaseExceptionDetail,
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
from maasservicelayer.models.base import Unset
from maasservicelayer.models.external_auth import (
    OAuthProvider,
    ProviderMetadata,
)
from maasservicelayer.models.secrets import V3OAuthEncryptionSecret
from maasservicelayer.models.users import User
from maasservicelayer.services.base import BaseService, Service, ServiceCache
from maasservicelayer.services.secrets import SecretNotFound, SecretsService
from maasservicelayer.services.tokens import OIDCRevokedTokenService
from maasservicelayer.services.users import UsersService
from maasservicelayer.utils.date import utcnow
from maasservicelayer.utils.encryptor import Encryptor

logger = structlog.getLogger(__name__)


class ExternalOAuthServiceCache(ServiceCache):
    httpx_client: AsyncClient | None = None
    oauth2_client: OAuth2Client | None = None

    async def clear_oauth_client(self) -> None:
        if self.oauth2_client:
            await self.oauth2_client.client.aclose()  # pyright: ignore [reportAttributeAccessIssue]
        self.oauth2_client = None

    async def close(self) -> None:
        if self.httpx_client:
            await self.httpx_client.aclose()
        if self.oauth2_client:
            await self.oauth2_client.client.aclose()  # pyright: ignore [reportAttributeAccessIssue]


class ExternalOAuthService(
    BaseService[OAuthProvider, ExternalOAuthRepository, OAuthProviderBuilder]
):
    MAAS_V3_ENCRYPTION_KEY_SECRET = V3OAuthEncryptionSecret()
    ENCRYPTION_SECRET_KEY_BYTES = 128
    ENCRYPTION_SECRET_KEY = None

    def __init__(
        self,
        context: Context,
        external_oauth_repository: ExternalOAuthRepository,
        revoked_tokens_service: OIDCRevokedTokenService,
        secrets_service: SecretsService,
        users_service: UsersService,
        cache: ExternalOAuthServiceCache | None = None,
    ):
        super().__init__(context, external_oauth_repository, cache)
        self.secrets_service = secrets_service
        self.users_service = users_service
        self.revoked_tokens_service = revoked_tokens_service

    @staticmethod
    def build_cache_object() -> ExternalOAuthServiceCache:
        return ExternalOAuthServiceCache()

    async def pre_create_hook(self, builder) -> None:
        existing_enabled = await self.get_provider()
        if existing_enabled and builder.enabled is True:
            raise ConflictException(
                details=[
                    BaseExceptionDetail(
                        type=CONFLICT_VIOLATION_TYPE,
                        message="An enabled OIDC provider already exists. Please disable it first.",
                    )
                ]
            )

        builder.issuer_url = builder.ensure_set(builder.issuer_url).rstrip("/")

        builder.metadata = await self.get_provider_metadata(builder)

    async def _update_connected_users_active_status(
        self, provider_id: int, is_active: bool
    ):
        """Update the is_active status of all the users connected to `provider_id`."""
        await self.users_service.update_many(
            query=QuerySpec(
                where=UserClauseFactory.with_provider_id(provider_id)
            ),
            builder=UserBuilder(is_active=is_active),
        )

    async def pre_delete_hook(
        self, resource_to_be_deleted: OAuthProvider
    ) -> None:
        if resource_to_be_deleted.enabled is True:
            raise PreconditionFailedException(
                details=[
                    BaseExceptionDetail(
                        type=PRECONDITION_FAILED,
                        message="This OIDC provider is enabled. Please disable it first.",
                    )
                ]
            )

    async def post_update_hook(
        self, old_resource: OAuthProvider, updated_resource: OAuthProvider
    ) -> None:
        if old_resource.enabled or updated_resource.enabled:
            # FIXME: clears only local cache; HA setups will need multi-region invalidation.
            await self.cache.clear_oauth_client()  # type: ignore

        if old_resource.enabled and not updated_resource.enabled:
            # Provider has been disabled, mark users inactive.
            # There's no need to re-do this in the `post_delete_hook` since a
            # provider can only be deleted if it's disabled first.
            await self._update_connected_users_active_status(
                updated_resource.id, False
            )
        elif not old_resource.enabled and updated_resource.enabled:
            # Provider has been enabled, mark users active
            await self._update_connected_users_active_status(
                updated_resource.id, True
            )

    async def get_provider(self) -> OAuthProvider | None:
        return await self.repository.get_provider()

    async def get_provider_metadata(
        self, builder: OAuthProviderBuilder
    ) -> ProviderMetadata:
        httpx_client = self.get_httpx_client()
        try:
            response = await httpx_client.get(
                f"{builder.issuer_url}/.well-known/openid-configuration"
            )
        except Exception as e:
            raise BadGatewayException(
                details=[
                    BaseExceptionDetail(
                        type=PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
                        message="A network error occurred while trying to reach the OIDC server.",
                    ),
                ]
            ) from e

        if response.status_code != 200:
            raise BadGatewayException(
                details=[
                    BaseExceptionDetail(
                        type=PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
                        message=f"OIDC server returned an unexpected response with status code: {response.status_code}.",
                    ),
                ]
            )

        metadata = response.json()
        return ProviderMetadata(**metadata)

    async def get_callback(self, code: str, nonce: str) -> OAuthTokenData:
        client = await self.get_client()

        data = await client.callback(code=code, nonce=nonce)
        user, newly_created = await self.users_service.get_or_create(
            query=QuerySpec(
                UserClauseFactory.with_username_or_email_like(
                    data.user_info.email
                )
            ),
            builder=UserBuilder(
                username=data.user_info.email,
                email=data.user_info.email,
                first_name=data.user_info.given_name or "",
                last_name=data.user_info.family_name or "",
                password="",
                is_active=True,
                is_staff=False,
                is_superuser=False,
                last_login=utcnow(),
                date_joined=utcnow(),
            ),
        )
        if newly_created:
            await self.users_service.update_profile(
                user_id=user.id,
                builder=UserProfileBuilder(
                    is_local=False, provider_id=client.provider.id
                ),
            )
        logger.info(
            AUTHN_LOGIN_SUCCESSFUL,
            type=SECURITY,
            user_id=user.username,
            role=ADMIN if user.is_superuser else USER,
        )

        return data.tokens

    async def revoke_token(self, id_token: str, refresh_token: str) -> None:
        client = await self.get_client()
        id_token_object = await client.parse_raw_id_token(id_token=id_token)
        await self.revoked_tokens_service.create_revoked_token(
            token=refresh_token,
            provider_id=client.provider.id,
            email=id_token_object.email,
        )
        await client.revoke_token(token=refresh_token)

        logger.info(
            f"{AUTHN_TOKEN_REVOKED}:OIDC:{REFRESH_TOKEN}",
            type=SECURITY,
            token_hash=hash_token_for_logging(refresh_token),
        )

    async def validate_access_token(self, access_token: str) -> None:
        client = await self.get_client()
        try:
            await client.validate_access_token(access_token=access_token)
        except Exception as e:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="The provided access token is invalid.",
                    )
                ]
            ) from e

    async def refresh_access_token(
        self, refresh_token: str
    ) -> OAuthRefreshData:
        if await self.revoked_tokens_service.is_revoked(refresh_token):
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="The provided refresh token is invalid.",
                    )
                ]
            )
        client = await self.get_client()
        try:
            tokens = await client.refresh_access_token(
                refresh_token=refresh_token
            )
        except Exception as e:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="The provided refresh token is invalid.",
                    )
                ]
            ) from e
        return tokens

    async def get_user_from_id_token(self, id_token: str) -> User | None:
        client = await self.get_client()
        try:
            claims = await client.parse_raw_id_token(id_token=id_token)
            user = await self.users_service.get_by_username(
                username=claims.email
            )
        except Exception as e:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Failed to parse ID token.",
                    )
                ]
            ) from e
        return user

    @Service.from_cache_or_execute_async(attr="oauth2_client")
    async def get_client(self) -> OAuth2Client:
        provider = await self.get_provider()
        if not provider:
            raise ConflictException(
                details=[
                    BaseExceptionDetail(
                        type=MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
                        message="No enabled OIDC provider is configured. Configure and enable an OIDC provider before "
                        "using OAuth operations.",
                    )
                ]
            )
        return OAuth2Client(provider)

    async def get_provider_adapter(self) -> BaseProviderAdapter | None:
        client = await self.get_client()
        return get_provider_adapter(
            provider=client.provider,
            http_client=self.get_httpx_client(),
        )

    async def is_active_oidc_user(self, email: str) -> bool:
        provider = await self.get_provider()
        if provider is None:
            return False
        user_profile = await self.users_service.get_user_profile(email)
        if user_profile is None or user_profile.provider_id != provider.id:
            return False
        adapter = get_provider_adapter(
            provider=provider, http_client=self.get_httpx_client()
        )
        if adapter is None:
            return True
        return await adapter.user_is_active(email)

    @Service.from_cache_or_execute(attr="httpx_client")
    def get_httpx_client(self) -> AsyncClient:
        return AsyncClient()

    async def update_provider(
        self, id: int, builder: OAuthProviderBuilder
    ) -> OAuthProvider | None:
        enable_requested = builder.enabled is True
        existing_enabled = await self.get_provider()
        if not isinstance(builder.issuer_url, Unset):
            builder.issuer_url = builder.issuer_url.rstrip("/")

        if (
            not enable_requested
            or not existing_enabled
            or existing_enabled.id == id
        ):
            if not isinstance(builder.issuer_url, Unset):
                builder.metadata = await self.get_provider_metadata(builder)
            return await self.update_by_id(id=id, builder=builder)

        raise ConflictException(
            details=[
                BaseExceptionDetail(
                    type=CONFLICT_VIOLATION_TYPE,
                    message="An enabled OIDC provider already exists. Please disable it first.",
                )
            ]
        )

    async def get_encryptor(self) -> Encryptor:
        encryption_key = await self._get_or_create_cached_encryption_key()
        return Encryptor(encryption_key)

    async def _get_or_create_cached_encryption_key(self) -> bytes:
        if not self.ENCRYPTION_SECRET_KEY:
            try:
                key_b64 = await self.secrets_service.get_simple_secret(
                    self.MAAS_V3_ENCRYPTION_KEY_SECRET
                )
                key = base64.b64decode(key_b64)
            except SecretNotFound:
                key = AESGCM.generate_key(self.ENCRYPTION_SECRET_KEY_BYTES)
                key_b64 = base64.b64encode(key).decode("utf-8")
                await self.secrets_service.set_simple_secret(
                    self.MAAS_V3_ENCRYPTION_KEY_SECRET, key_b64
                )
            self.ENCRYPTION_SECRET_KEY = key
        return self.ENCRYPTION_SECRET_KEY  # type: ignore
