#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.users import (
    UserProfileResourceBuilder,
    UsersRepository,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.users import User, UserProfile
from maasservicelayer.services._base import Service


class UsersService(Service):
    def __init__(
        self,
        context: Context,
        users_repository: UsersRepository | None = None,
    ):
        super().__init__(context)
        self.users_repository = (
            users_repository if users_repository else UsersRepository(context)
        )

    async def create(self, resource: CreateOrUpdateResource) -> User:
        user = await self.users_repository.create(resource)
        if user is not None:
            user_profile_resource = (
                UserProfileResourceBuilder()
                .with_completed_intro(False)
                .with_auth_last_check(None)
                .with_is_local(True)
                .build()
            )
            await self.create_profile(
                user.id,
                user_profile_resource,
            )
        return user

    async def get(self, username: str) -> User | None:
        return await self.users_repository.find_by_username(username)

    async def find_by_id(self, id: int) -> User | None:
        return await self.users_repository.find_by_id(id)

    async def get_by_session_id(self, sessionid: str) -> User | None:
        return await self.users_repository.find_by_sessionid(sessionid)

    async def get_user_profile(self, username: str) -> UserProfile | None:
        return await self.users_repository.get_user_profile(username)

    async def get_user_apikeys(self, username: str) -> list[str] | None:
        return await self.users_repository.get_user_apikeys(username)

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[User]:
        return await self.users_repository.list(
            token=token, size=size, query=query
        )

    async def update_by_id(
        self, user_id: int, resource: CreateOrUpdateResource
    ) -> User:
        return await self.users_repository.update_by_id(
            id=user_id, resource=resource
        )

    async def create_profile(
        self, user_id: int, resource: CreateOrUpdateResource
    ) -> UserProfile:
        return await self.users_repository.create_profile(
            user_id=user_id, resource=resource
        )

    async def update_profile(
        self, user_id: int, resource: CreateOrUpdateResource
    ) -> UserProfile:
        return await self.users_repository.update_profile(
            user_id=user_id, resource=resource
        )
