import os

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.models.constants import (
    UNEXISTING_USER_OR_INVALID_CREDENTIALS_VIOLATION_TYPE,
)
from maasapiserver.common.models.exceptions import (
    BaseExceptionDetail,
    UnauthorizedException,
)
from maasapiserver.common.services._base import Service
from maasapiserver.v3.auth.jwt import JWT, UserRole
from maasapiserver.v3.models.auth import AuthenticatedUser
from maasapiserver.v3.services.secrets import SecretNotFound, SecretsService
from maasapiserver.v3.services.users import UsersService


class AuthService(Service):
    MAAS_V3_JWT_KEY_SECRET_PATH = "global/v3-jwt-key"
    TOKEN_SECRET_KEY_BYTES = 32

    # Cache the JWT token as attribute of the class itself. This way, the key will be loaded only once after every restart.
    JWT_TOKEN_KEY = None

    def __init__(
        self,
        connection: AsyncConnection,
        secrets_service: SecretsService,
        users_service: UsersService | None = None,
    ):
        super().__init__(connection)
        self.secrets_service = secrets_service
        self.users_service = (
            users_service if users_service else UsersService(connection)
        )

    async def login(self, username: str, password: str) -> JWT:
        user = await self.users_service.get(username)
        if not user or not user.is_active or not user.check_password(password):
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_USER_OR_INVALID_CREDENTIALS_VIOLATION_TYPE,
                        message="The credentials are not matching or the user does not exist",
                    )
                ]
            )

        roles = (
            [UserRole.USER, UserRole.ADMIN]
            if user.is_superuser
            else [UserRole.USER]
        )
        jwt_key = await self._get_or_create_cached_jwt_key()
        return JWT.create(jwt_key, user.username, roles)

    async def access_token(self, authenticated_user: AuthenticatedUser) -> JWT:
        jwt_key = await self._get_or_create_cached_jwt_key()
        return JWT.create(
            jwt_key,
            authenticated_user.username,
            list(authenticated_user.roles),
        )

    async def decode_and_verify_token(self, token: str) -> JWT:
        jwt_key = await self._get_or_create_cached_jwt_key()
        return JWT.decode(jwt_key, token)

    async def _get_or_create_cached_jwt_key(self) -> str:
        """This private method fetches the jwt key from the database if the key was not loaded yet. If the key does not exist,
        it simply creates it.
        """
        if not self.JWT_TOKEN_KEY:
            try:
                jwt_key = await self.secrets_service.get_simple_secret(
                    self.MAAS_V3_JWT_KEY_SECRET_PATH
                )
            except SecretNotFound:
                jwt_key = os.urandom(self.TOKEN_SECRET_KEY_BYTES).hex()
                await self.secrets_service.set_simple_secret(
                    self.MAAS_V3_JWT_KEY_SECRET_PATH, jwt_key
                )
            AuthService.JWT_TOKEN_KEY = jwt_key
        return self.JWT_TOKEN_KEY
