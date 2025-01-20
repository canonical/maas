#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.users import UsersRepository
from maasservicelayer.models.users import (
    User,
    UserBuilder,
    UserProfile,
    UserProfileBuilder,
)
from maasservicelayer.services._base import BaseService


class UsersService(BaseService[User, UsersRepository, UserBuilder]):
    def __init__(
        self,
        context: Context,
        users_repository: UsersRepository,
    ):
        super().__init__(context, users_repository)

    async def post_create_hook(self, resource: User) -> None:
        await self.create_profile(
            resource.id,
            UserProfileBuilder(
                completed_intro=False, auth_last_check=None, is_local=True
            ),
        )
        return

    async def get_by_session_id(self, sessionid: str) -> User | None:
        return await self.repository.find_by_sessionid(sessionid)

    async def get_user_profile(self, username: str) -> UserProfile | None:
        return await self.repository.get_user_profile(username)

    async def get_user_apikeys(self, username: str) -> list[str] | None:
        return await self.repository.get_user_apikeys(username)

    async def create_profile(
        self, user_id: int, builder: UserProfileBuilder
    ) -> UserProfile:
        return await self.repository.create_profile(
            user_id=user_id, builder=builder
        )

    async def update_profile(
        self, user_id: int, builder: UserProfileBuilder
    ) -> UserProfile:
        return await self.repository.update_profile(
            user_id=user_id, builder=builder
        )
