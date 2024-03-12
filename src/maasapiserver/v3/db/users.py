from sqlalchemy import select
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db.tables import UserTable
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.api.models.requests.users import UserRequest
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.users import User


class UsersRepository(BaseRepository[User, UserRequest]):
    async def create(self, request: UserRequest) -> User:
        raise Exception("Not implemented yet.")

    async def find_by_id(self, id: int) -> User | None:
        raise Exception("Not implemented yet.")

    async def find_by_username(self, username: str) -> User | None:
        stmt = (
            select("*")
            .select_from(UserTable)
            .where(eq(UserTable.c.username, username))
        )
        user = (await self.connection.execute(stmt)).first()
        if not user:
            return None
        return User(**user._asdict())

    async def list(
        self, pagination_params: PaginationParams
    ) -> ListResult[User]:
        raise Exception("Not implemented yet.")

    async def update(self, resource: User) -> User:
        raise Exception("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise Exception("Not implemented yet.")
