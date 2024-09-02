from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.base import CreateOrUpdateResource
from maasapiserver.v3.db.users import UsersRepository
from maasservicelayer.models.users import User, UserProfile


class UsersService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        users_repository: UsersRepository | None = None,
    ):
        super().__init__(connection)
        self.users_repository = (
            users_repository
            if users_repository
            else UsersRepository(connection)
        )

    async def get(self, username: str) -> User | None:
        return await self.users_repository.find_by_username(username)

    async def get_by_session_id(self, sessionid: str) -> User | None:
        return await self.users_repository.find_by_sessionid(sessionid)

    async def get_user_profile(self, username: str) -> UserProfile | None:
        return await self.users_repository.get_user_profile(username)

    async def update(
        self, user_id: int, resource: CreateOrUpdateResource
    ) -> User:
        return await self.users_repository.update(
            id=user_id, resource=resource
        )

    async def update_profile(
        self, user_id: int, resource: CreateOrUpdateResource
    ) -> UserProfile:
        return await self.users_repository.update_profile(
            user_id=user_id, resource=resource
        )
