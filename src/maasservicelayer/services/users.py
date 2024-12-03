#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.users import (
    UserProfileResourceBuilder,
    UsersRepository,
)
from maasservicelayer.models.users import User, UserProfile
from maasservicelayer.services._base import BaseService


class UsersService(BaseService[User, UsersRepository]):
    def __init__(
        self,
        context: Context,
        users_repository: UsersRepository,
    ):
        super().__init__(context, users_repository)

    async def post_create_hook(self, resource: User) -> None:
        user_profile_resource = (
            UserProfileResourceBuilder()
            .with_completed_intro(False)
            .with_auth_last_check(None)
            .with_is_local(True)
            .build()
        )
        await self.create_profile(
            resource.id,
            user_profile_resource,
        )
        return

    async def get_by_session_id(self, sessionid: str) -> User | None:
        return await self.repository.find_by_sessionid(sessionid)

    async def get_user_profile(self, username: str) -> UserProfile | None:
        return await self.repository.get_user_profile(username)

    async def get_user_apikeys(self, username: str) -> list[str] | None:
        return await self.repository.get_user_apikeys(username)

    async def create_profile(
        self, user_id: int, resource: CreateOrUpdateResource
    ) -> UserProfile:
        return await self.repository.create_profile(
            user_id=user_id, resource=resource
        )

    async def update_profile(
        self, user_id: int, resource: CreateOrUpdateResource
    ) -> UserProfile:
        return await self.repository.update_profile(
            user_id=user_id, resource=resource
        )
