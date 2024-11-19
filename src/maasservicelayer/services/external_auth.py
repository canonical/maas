#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
import os

from macaroonbakery import bakery, checkers, httpbakery
from macaroonbakery.bakery._store import RootKeyStore
from macaroonbakery.httpbakery.agent import Agent, AuthInfo
from pymacaroons import Macaroon
from starlette.datastructures import Headers

from maasserver.macaroons import _get_macaroon_caveats_ops, _IDClient
from maasservicelayer.auth.external_auth import (
    ExternalAuthConfig,
    ExternalAuthType,
)
from maasservicelayer.auth.macaroons.checker import AsyncChecker
from maasservicelayer.auth.macaroons.locator import AsyncThirdPartyLocator
from maasservicelayer.auth.macaroons.macaroon_client import (
    CandidAsyncClient,
    RbacAsyncClient,
)
from maasservicelayer.auth.macaroons.oven import AsyncOven
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.external_auth import (
    ExternalAuthRepository,
)
from maasservicelayer.db.repositories.users import (
    UserProfileResourceBuilder,
    UserResourceBuilder,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    DischargeRequiredException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import INVALID_TOKEN_VIOLATION_TYPE
from maasservicelayer.models.users import User
from maasservicelayer.services._base import Service, ServiceCache
from maasservicelayer.services.secrets import SecretsService
from maasservicelayer.services.users import UsersService
from maasservicelayer.utils.date import utcnow
from provisioningserver.security import to_bin, to_hex

MACAROON_LIFESPAN = timedelta(days=1)


@lru_cache
def get_third_party_locator(auth_endpoint: str):
    return AsyncThirdPartyLocator(
        allow_insecure=not auth_endpoint.startswith("https:")
    )


@dataclass(slots=True)
class ExternalAuthServiceCache(ServiceCache):
    external_auth_config: ExternalAuthConfig | None = None
    auth_info: AuthInfo | None = None
    bakery_key: bakery.PrivateKey | None = None
    candid_client: CandidAsyncClient | None = None
    rbac_client: RbacAsyncClient | None = None

    async def close(self) -> None:
        if self.rbac_client:
            await self.rbac_client.close()
        if self.candid_client:
            await self.candid_client.close()


# We need to implement RootKeyStore because we pass this service to the Macaroon Auth Checker
class ExternalAuthService(Service, RootKeyStore):
    EXTERNAL_AUTH_SECRET_PATH = "global/external-auth"
    BAKERY_KEY_SECRET_PATH = "global/macaroon-key"
    ROOTKEY_MATERIAL_SECRET_FORMAT = "rootkey/%s/material"

    # size in bytes of the key
    KEY_LENGTH = 24

    def __init__(
        self,
        context: Context,
        secrets_service: SecretsService,
        users_service: UsersService,
        cache: ExternalAuthServiceCache | None = None,
        external_auth_repository: ExternalAuthRepository | None = None,
    ):
        super().__init__(context, cache)
        self.secrets_service = secrets_service
        self.users_service = users_service
        self.external_auth_repository = (
            external_auth_repository or ExternalAuthRepository(context)
        )

    @staticmethod
    def build_cache_object() -> ExternalAuthServiceCache:
        return ExternalAuthServiceCache()

    @Service.from_cache_or_execute(attr="external_auth_config")
    async def get_external_auth(self) -> ExternalAuthConfig | None:
        """
        Same logic of maasserver.middleware.ExternalAuthInfoMiddleware._get_external_auth_info
        """
        config = await self.secrets_service.get_composite_secret(
            path=self.EXTERNAL_AUTH_SECRET_PATH, default={}
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

    @Service.from_cache_or_execute(attr="auth_info")
    async def get_auth_info(self) -> AuthInfo | None:
        """
        Same logic of maasserver.macaroon_auth.get_auth_info
        """
        config = await self.secrets_service.get_composite_secret(
            path=self.EXTERNAL_AUTH_SECRET_PATH, default=None
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
        )

        username = auth_info.identity.id()
        user = await self.users_service.get(username=username)
        if not user:
            user_builder = (
                UserResourceBuilder()
                .with_username(username)
                .with_first_name("")
                .with_password("")
                .with_is_active(True)
                .with_is_staff(False)
                .with_is_superuser(False)
                .with_last_login(utcnow())
            )
            user = await self.users_service.create(user_builder.build())
            profile_builder = (
                UserProfileResourceBuilder()
                .with_is_local(False)
                .with_completed_intro(True)
                .with_auth_last_check(utcnow())
            )
            await self.users_service.create_profile(
                user.id, profile_builder.build()
            )

        return user

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
            locator=get_third_party_locator(auth_endpoint),
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

    async def get(self, id: bytes) -> bytes | None:
        """Return the key with the specified bytes string id."""
        key = await self.external_auth_repository.find_by_id(id=int(id))
        if not key:
            return None
        if key.expiration < utcnow():
            await self._delete(id=key.id)
            return None
        return await self._get_key_material(id=key.id)

    async def root_key(self):
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
            path=self.ROOTKEY_MATERIAL_SECRET_FORMAT % id, default=None
        )
        if not secret:
            return None
        return to_bin(secret)

    async def _new_key(self):
        key = await self.external_auth_repository.create()
        material = os.urandom(self.KEY_LENGTH)
        await self.secrets_service.set_simple_secret(
            path=self.ROOTKEY_MATERIAL_SECRET_FORMAT % key.id,
            value=to_hex(material),
        )
        return key

    async def _delete(self, id: int) -> None:
        """
        Delete the key and the related material
        """
        await self.external_auth_repository.delete(id=id)
        await self.secrets_service.delete(
            path=self.ROOTKEY_MATERIAL_SECRET_FORMAT % id
        )

    async def generate_discharge_macaroon(
        self,
        macaroon_bakery: bakery.Bakery,
        caveats: list[checkers.Caveat],
        ops: list[bakery.Op],
        req_headers: Headers | None = None,
    ) -> bakery.Macaroon:
        bakery_version = httpbakery.request_version(req_headers or {})
        expiration = utcnow() + MACAROON_LIFESPAN
        macaroon = await macaroon_bakery.oven.macaroon(
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
        return CandidAsyncClient(auth_info)

    @Service.from_cache_or_execute(attr="rbac_client")
    async def get_rbac_client(self) -> RbacAsyncClient:
        auth_info = await self.get_auth_info()
        auth_config = await self.get_external_auth()
        # auth_config.url comes with a /auth suffix used for some macaroon internals.
        # We don't want to diverge too much from the structure we have in maasserver, hence we simply remove the suffix here.
        return RbacAsyncClient(auth_config.url.rstrip("/auth"), auth_info)
