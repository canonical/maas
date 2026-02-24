# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import base64
from dataclasses import dataclass, field
from datetime import timedelta
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from httpx import AsyncClient
from macaroonbakery import bakery, checkers, httpbakery
from macaroonbakery.bakery._store import RootKeyStore
from macaroonbakery.httpbakery.agent import Agent, AuthInfo
from pymacaroons import Macaroon
from starlette.datastructures import Headers
import structlog

from maascommon.logging.security import (
    ADMIN,
    AUTHN_LOGIN_SUCCESSFUL,
    SECURITY,
    USER,
)
from maasserver.macaroons import _get_macaroon_caveats_ops, _IDClient
from maasservicelayer.auth.external_auth import (
    ExternalAuthConfig,
    ExternalAuthType,
)
from maasservicelayer.auth.external_oauth import (
    OAuth2Client,
    OAuthRefreshData,
    OAuthTokenData,
)
from maasservicelayer.auth.macaroons.checker import AsyncChecker
from maasservicelayer.auth.macaroons.locator import AsyncThirdPartyLocator
from maasservicelayer.auth.macaroons.macaroon_client import (
    CandidAsyncClient,
    RbacAsyncClient,
)
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
    BaseExceptionDetail,
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
    OAuthProvider,
    ProviderMetadata,
)
from maasservicelayer.models.secrets import (
    ExternalAuthSecret,
    MacaroonKeySecret,
    RootKeyMaterialSecret,
    V3OAuthEncryptionSecret,
)
from maasservicelayer.models.users import User
from maasservicelayer.services.base import BaseService, Service, ServiceCache
from maasservicelayer.services.secrets import SecretNotFound, SecretsService
from maasservicelayer.services.tokens import OIDCRevokedTokenService
from maasservicelayer.services.users import UsersService
from maasservicelayer.utils.date import utcnow
from maasservicelayer.utils.encryptor import Encryptor
from provisioningserver.security import to_bin, to_hex

MACAROON_LIFESPAN = timedelta(days=1)

logger = structlog.getLogger(__name__)


@dataclass(slots=True)
class ExternalAuthServiceCache(ServiceCache):
    external_auth_config: ExternalAuthConfig | None = None
    bakery_key: bakery.PrivateKey | None = None
    candid_client: CandidAsyncClient | None = None
    rbac_client: RbacAsyncClient | None = None
    third_party_locators: dict[str, AsyncThirdPartyLocator] = field(
        default_factory=dict
    )

    def get_third_party_locator(
        self, auth_endpoint: str
    ) -> AsyncThirdPartyLocator:
        if auth_endpoint not in self.third_party_locators:
            self.third_party_locators[auth_endpoint] = AsyncThirdPartyLocator(
                allow_insecure=not auth_endpoint.startswith("https:")
            )
        return self.third_party_locators[auth_endpoint]

    async def close(self) -> None:
        for third_party_locator in self.third_party_locators.values():
            await third_party_locator.close()

        if self.rbac_client:
            await self.rbac_client.close()
        if self.candid_client:
            await self.candid_client.close()


# We need to implement RootKeyStore because we pass this service to the Macaroon Auth Checker
class ExternalAuthService(Service, RootKeyStore):
    EXTERNAL_AUTH_SECRET = ExternalAuthSecret()
    BAKERY_KEY_SECRET = MacaroonKeySecret()

    # size in bytes of the key
    KEY_LENGTH = 24

    def __init__(
        self,
        context: Context,
        secrets_service: SecretsService,
        users_service: UsersService,
        external_auth_repository: ExternalAuthRepository,
        cache: ExternalAuthServiceCache | None = None,
    ):
        super().__init__(context, cache)
        self.secrets_service = secrets_service
        self.users_service = users_service
        self.external_auth_repository = external_auth_repository

    @staticmethod
    def build_cache_object() -> ExternalAuthServiceCache:
        return ExternalAuthServiceCache()

    @Service.from_cache_or_execute(attr="external_auth_config")
    async def get_external_auth(self) -> ExternalAuthConfig | None:
        config = await self.secrets_service.get_composite_secret(
            model=self.EXTERNAL_AUTH_SECRET, default={}
        )
        candid_endpoint = config.get("url", "")
        rbac_endpoint = config.get("rbac-url", "")
        auth_domain = config.get("domain", "")
        auth_admin_group = config.get("admin-group", "")

        if rbac_endpoint:
            auth_type = ExternalAuthType.RBAC
            auth_endpoint = rbac_endpoint.rstrip("/") + "/auth"
            # not used, ensure they're unset
            auth_domain = ""
            auth_admin_group = ""
        elif candid_endpoint:
            auth_type = ExternalAuthType.CANDID
            auth_endpoint = candid_endpoint
        else:
            return None

        # strip trailing slashes as otherwise js-bakery ends up using double
        # slashes in the URL
        return ExternalAuthConfig(
            type=auth_type,
            url=auth_endpoint.rstrip("/"),
            domain=auth_domain,
            admin_group=auth_admin_group,
        )

    # Django is using this and we can't cache the object. This is because when the external auth is configured the regions are
    # not restarted and we don't have a mechanism to invalidate the cache (yet).
    async def get_auth_info(self) -> AuthInfo | None:
        """
        Same logic of maasserver.macaroon_auth.get_auth_info
        """
        config = await self.secrets_service.get_composite_secret(
            model=self.EXTERNAL_AUTH_SECRET, default=None
        )

        if config is None:
            return None
        key = bakery.PrivateKey.deserialize(config["key"])
        agent = Agent(
            url=config["url"],
            username=config["user"],
        )
        return AuthInfo(key=key, agents=[agent])

    async def login(
        self, macaroons: list[list[Macaroon]], request_absolute_uri: str
    ) -> User | None:
        macaroon_bakery = await self.get_bakery(request_absolute_uri)
        return await self._login(macaroons, macaroon_bakery)

    async def _login(
        self,
        macaroons: list[list[Macaroon]],
        macaroon_bakery: bakery.Bakery | None,
    ) -> User | None:
        if not macaroon_bakery:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Macaroon based authentication is not enabled on this server.",
                    )
                ]
            )
        auth_checker = macaroon_bakery.checker.auth(macaroons)

        # This might raise DischargeRequiredError, VerificationError or PermissionDenied. The caller has
        # to handle them accordingly.
        auth_info = await auth_checker.allow(
            ctx=checkers.AuthContext(), ops=[bakery.LOGIN_OP]
        )  # type: ignore

        username = auth_info.identity.id()
        user, created = await self.users_service.get_or_create(
            query=QuerySpec(UserClauseFactory.with_username(username)),
            builder=UserBuilder(
                username=username,
                first_name="",
                password="",
                is_active=True,
                is_staff=False,
                is_superuser=False,
                last_login=utcnow(),
            ),
        )
        if not created:
            profile_builder = UserProfileBuilder(
                is_local=False, completed_intro=True, auth_last_check=utcnow()
            )
            # the users_service already create a user profile in the post create hook
            await self.users_service.update_profile(user.id, profile_builder)

        return user

    def _get_third_party_locator(self, auth_endpoint):
        if self.cache:
            return self.cache.get_third_party_locator(auth_endpoint)  # type: ignore
        return AsyncThirdPartyLocator(
            allow_insecure=not auth_endpoint.startswith("https:")
        )

    async def get_bakery(
        self, request_absolute_uri: str
    ) -> bakery.Bakery | None:
        external_auth_config = await self.get_external_auth()
        if not external_auth_config:
            return None
        auth_endpoint = external_auth_config.url
        auth_domain = external_auth_config.domain
        base_bakery = bakery.Bakery()
        base_checker = checkers.Checker()
        oven = AsyncOven(
            key=await self.get_or_create_bakery_key(),
            location=request_absolute_uri,
            locator=self._get_third_party_locator(auth_endpoint),
            namespace=base_checker.namespace(),
            root_keystore_for_ops=lambda ops: self,
            ops_store=None,
        )
        base_bakery._oven = oven
        base_bakery._checker = AsyncChecker(
            checker=base_checker,
            authorizer=bakery.ACLAuthorizer(
                get_acl=lambda ctx, op: [bakery.EVERYONE]
            ),
            identity_client=_IDClient(auth_endpoint, auth_domain=auth_domain),
            macaroon_opstore=oven,
        )
        return base_bakery

    @Service.from_cache_or_execute(attr="bakery_key")
    async def get_or_create_bakery_key(self) -> bakery.PrivateKey:
        key = await self.secrets_service.get_simple_secret(
            model=self.BAKERY_KEY_SECRET, default=None
        )
        if key:
            return bakery.PrivateKey.deserialize(key)

        key = bakery.generate_key()
        await self.secrets_service.set_simple_secret(
            model=self.BAKERY_KEY_SECRET,
            value=key.serialize().decode("ascii"),
        )
        return key

    async def get(self, id: bytes) -> bytes | None:
        """Return the key with the specified bytes string id."""
        key = await self.external_auth_repository.find_by_id(id=int(id))
        if not key:
            return None
        if key.expiration < utcnow():
            await self._delete(id=key.id)
            return None
        return await self._get_key_material(id=key.id)

    async def root_key(self):  # type: ignore
        key = await self.external_auth_repository.find_best_key()
        if not key:
            # delete expired keys (if any)
            expired_keys = (
                await self.external_auth_repository.find_expired_keys()
            )
            for expired_key in expired_keys:
                await self._delete(id=expired_key.id)
            key = await self._new_key()
        material = await self._get_key_material(id=key.id)
        return material, str(key.id).encode("ascii")

    async def _get_key_material(self, id: int) -> bytes | None:
        secret = await self.secrets_service.get_simple_secret(
            model=RootKeyMaterialSecret(id=id), default=None
        )
        if not secret:
            return None
        return to_bin(secret)

    async def _new_key(self):
        key = await self.external_auth_repository.create()
        material = os.urandom(self.KEY_LENGTH)
        await self.secrets_service.set_simple_secret(
            model=RootKeyMaterialSecret(id=key.id),
            value=to_hex(material),
        )
        return key

    async def _delete(self, id: int) -> None:
        """
        Delete the key and the related material
        """
        await self.external_auth_repository.delete(id=id)
        await self.secrets_service.delete(model=RootKeyMaterialSecret(id=id))

    async def generate_discharge_macaroon(
        self,
        macaroon_bakery: bakery.Bakery,
        caveats: list[checkers.Caveat],
        ops: list[bakery.Op],
        req_headers: Headers | None = None,
    ) -> bakery.Macaroon:
        bakery_version = httpbakery.request_version(req_headers or {})
        expiration = utcnow() + MACAROON_LIFESPAN
        macaroon = await macaroon_bakery.oven.macaroon(  # type: ignore
            bakery_version, expiration, caveats, ops
        )
        return macaroon

    async def raise_discharge_required_exception(
        self,
        external_auth_info: ExternalAuthConfig,
        absolute_uri: str,
        req_headers: Headers | None = None,
    ):
        macaroon_bakery = await self.get_bakery(absolute_uri)

        assert macaroon_bakery is not None

        caveats, ops = _get_macaroon_caveats_ops(
            external_auth_info.url, external_auth_info.domain
        )
        macaroon = await self.generate_discharge_macaroon(
            macaroon_bakery=macaroon_bakery,
            caveats=caveats,
            ops=ops,
            req_headers=req_headers,
        )
        raise DischargeRequiredException(macaroon=macaroon)

    @Service.from_cache_or_execute(attr="candid_client")
    async def get_candid_client(self) -> CandidAsyncClient:
        auth_info = await self.get_auth_info()
        assert auth_info is not None
        return CandidAsyncClient(auth_info)

    @Service.from_cache_or_execute(attr="rbac_client")
    async def get_rbac_client(self) -> RbacAsyncClient:
        auth_info = await self.get_auth_info()
        auth_config = await self.get_external_auth()
        assert auth_info is not None
        assert auth_config is not None
        # auth_config.url comes with a /auth suffix used for some macaroon internals.
        # We don't want to diverge too much from the structure we have in maasserver, hence we simply remove the suffix here.
        return RbacAsyncClient(auth_config.url.rstrip("/auth"), auth_info)


class ExternalOAuthServiceCache(ServiceCache):
    httpx_client: AsyncClient | None = None
    oauth2_client: OAuth2Client | None = None

    async def clear_oauth_client(self) -> None:
        if self.oauth2_client:
            await self.oauth2_client.client.aclose()
        self.oauth2_client = None

    async def close(self) -> None:
        if self.httpx_client:
            await self.httpx_client.aclose()
        if self.oauth2_client:
            await self.oauth2_client.client.aclose()


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

    async def get_provider(self) -> OAuthProvider | None:
        return await self.repository.get_provider()

    async def get_provider_metadata(
        self, builder: OAuthProviderBuilder
    ) -> ProviderMetadata:
        httpx_client = await self.get_httpx_client()
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
            userID=user.username,
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

    @Service.from_cache_or_execute(attr="oauth2_client")
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

    @Service.from_cache_or_execute(attr="httpx_client")
    async def get_httpx_client(self) -> AsyncClient:
        return AsyncClient()

    async def update_provider(
        self, id: int, builder: OAuthProviderBuilder
    ) -> OAuthProvider | None:
        enable_requested = builder.enabled is True
        existing_enabled = await self.get_provider()
        builder.issuer_url = builder.ensure_set(builder.issuer_url).rstrip("/")

        if (
            not enable_requested
            or not existing_enabled
            or existing_enabled.id == id
        ):
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
