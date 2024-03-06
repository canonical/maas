from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.users import UsersRepository
from maasapiserver.v3.models.users import User


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
