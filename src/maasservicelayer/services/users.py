# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from time import time
from typing import List

from maascommon.constants import (
    GENERIC_CONSUMER,
    MAAS_USER_EMAIL,
    MAAS_USER_LAST_NAME,
    MAAS_USER_USERNAME,
)
from maascommon.enums.consumer import ConsumerState
from maascommon.enums.token import TokenType
from maascommon.utils.strings import get_random_string
from maasservicelayer.builders.consumers import ConsumerBuilder
from maasservicelayer.builders.ipranges import IPRangeBuilder
from maasservicelayer.builders.nodes import NodeBuilder
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.builders.tokens import TokenBuilder
from maasservicelayer.builders.users import UserBuilder, UserProfileBuilder
from maasservicelayer.constants import SYSTEM_USERS
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.consumers import ConsumerClauseFactory
from maasservicelayer.db.repositories.filestorage import (
    FileStorageClauseFactory,
)
from maasservicelayer.db.repositories.ipranges import IPRangeClauseFactory
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.db.repositories.notifications import (
    NotificationsClauseFactory,
)
from maasservicelayer.db.repositories.sshkeys import SshKeyClauseFactory
from maasservicelayer.db.repositories.sslkeys import SSLKeyClauseFactory
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.db.repositories.users import (
    UserClauseFactory,
    UsersRepository,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
    PRECONDITION_FAILED,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.users import User, UserProfile, UserWithSummary
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.consumers import ConsumersService
from maasservicelayer.services.filestorage import FileStorageService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.notifications import NotificationsService
from maasservicelayer.services.sshkeys import SshKeysService
from maasservicelayer.services.sslkey import SSLKeysService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.tokens import TokensService
from maasservicelayer.utils.date import utcnow

KEY_SIZE = 18
SECRET_SIZE = 32


class UsersService(BaseService[User, UsersRepository, UserBuilder]):
    def __init__(
        self,
        context: Context,
        users_repository: UsersRepository,
        staticipaddress_service: StaticIPAddressService,
        ipranges_service: IPRangesService,
        nodes_service: NodesService,
        sshkey_service: SshKeysService,
        sslkey_service: SSLKeysService,
        notification_service: NotificationsService,
        filestorage_service: FileStorageService,
        consumers_service: ConsumersService,
        tokens_service: TokensService,
    ):
        super().__init__(context, users_repository)
        self.staticipaddress_service = staticipaddress_service
        self.ipranges_service = ipranges_service
        self.nodes_service = nodes_service
        self.sshkey_service = sshkey_service
        self.sslkey_service = sslkey_service
        self.notification_service = notification_service
        self.filestorage_service = filestorage_service
        self.consumers_service = consumers_service
        self.tokens_service = tokens_service

    async def get_or_create_MAAS_user(self) -> User:
        # DO NOT create a profile for the MAAS technical users.
        user = await self.get_one(
            query=QuerySpec(
                where=UserClauseFactory.with_username(MAAS_USER_USERNAME)
            )
        )
        if not user:
            user = await self.repository.create(
                UserBuilder(
                    username=MAAS_USER_USERNAME,
                    first_name=MAAS_USER_USERNAME,
                    last_name=MAAS_USER_LAST_NAME,
                    email=MAAS_USER_EMAIL,
                    is_staff=False,
                    is_active=True,
                    is_superuser=True,
                    date_joined=utcnow(),
                    password="",
                )
            )
        return user

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

    async def get_MAAS_user_apikey(self) -> str:
        user = await self.get_or_create_MAAS_user()
        tokens = await self.tokens_service.get_user_apikeys(user.username)
        for token in reversed(tokens):
            return token
        else:
            return await self._create_auth_token(user_id=user.id)

    async def _create_auth_token(
        self, user_id: int, consumer_name: str = GENERIC_CONSUMER
    ) -> str:
        """Create new Token and Consumer (OAuth authorisation) for the `user_id`.

        Params:
          - user_id: the user to create a token for.
          - consumer_name: Name of the consumer to be assigned to the newly generated token.
        Returns:
          The created token
        """
        consumer = await self.consumers_service.create(
            ConsumerBuilder(
                user_id=user_id,
                description="",
                name=consumer_name,
                status=ConsumerState.ACCEPTED,
                key=get_random_string(length=KEY_SIZE),
                # This is a 'generic' consumer aimed to service many clients, hence
                # we don't authenticate the consumer with key/secret key.
                secret="",
            )
        )

        token = await self.tokens_service.create(
            TokenBuilder(
                user_id=user_id,
                token_type=TokenType.ACCESS,
                consumer_id=consumer.id,
                is_approved=True,
                key=get_random_string(length=KEY_SIZE),
                secret=get_random_string(length=SECRET_SIZE),
                verifier="",
                timestamp=int(time()),
                callback_confirmed=False,
            )
        )

        return ":".join([consumer.key, token.key, token.secret])

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

    async def delete_profile(self, user_id: int) -> UserProfile:
        return await self.repository.delete_profile(user_id=user_id)

    async def pre_delete_hook(self, resource_to_be_deleted: User) -> None:
        has_ipranges = await self.ipranges_service.exists(
            query=QuerySpec(
                where=IPRangeClauseFactory.with_user_id(
                    resource_to_be_deleted.id
                )
            )
        )
        has_staticips = await self.staticipaddress_service.exists(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_user_id(
                    resource_to_be_deleted.id
                )
            )
        )
        has_nodes = await self.nodes_service.exists(
            query=QuerySpec(
                where=NodeClauseFactory.with_owner_id(
                    resource_to_be_deleted.id
                )
            )
        )

        owned_resources = {
            "Static IP address(es)": has_ipranges,
            "IP range(s)": has_staticips,
            "Node(s)": has_nodes,
        }
        if any(owned_resources.values()):
            details = [
                BaseExceptionDetail(
                    type=PRECONDITION_FAILED,
                    message=f"Cannot delete user. {name} are still allocated.",
                )
                for name, exists in owned_resources.items()
                if exists
            ]
            raise PreconditionFailedException(details=details)

    async def post_delete_hook(self, resource: User) -> None:
        # Cascade
        await self.delete_profile(resource.id)
        await self.consumers_service.delete_many(
            query=QuerySpec(
                where=ConsumerClauseFactory.with_user_id(resource.id)
            )
        )
        await self.sshkey_service.delete_many(
            query=QuerySpec(
                where=SshKeyClauseFactory.with_user_id(resource.id)
            )
        )
        await self.sslkey_service.delete_many(
            query=QuerySpec(
                where=SSLKeyClauseFactory.with_user_id(resource.id)
            )
        )
        await self.notification_service.delete_many(
            query=QuerySpec(
                where=NotificationsClauseFactory.with_user_id(resource.id)
            )
        )
        await self.filestorage_service.delete_many(
            query=QuerySpec(
                where=FileStorageClauseFactory.with_owner_id(resource.id)
            )
        )

    async def post_delete_many_hook(self, resources: List[User]) -> None:
        raise NotImplementedError("Not implemented yet")

    async def transfer_resources(
        self, from_user_id: int, to_user_id: int
    ) -> None:
        to_user_exists = await self.exists(
            query=QuerySpec(where=UserClauseFactory.with_id(id=to_user_id))
        )
        if not to_user_exists:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message=f"Cannot transfer resources. User with id {to_user_id} doesn't exist.",
                    )
                ]
            )
        await self.staticipaddress_service.update_many(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_user_id(from_user_id)
            ),
            builder=StaticIPAddressBuilder(user_id=to_user_id),
        )
        await self.ipranges_service.update_many(
            query=QuerySpec(
                where=IPRangeClauseFactory.with_user_id(from_user_id)
            ),
            builder=IPRangeBuilder(user_id=to_user_id),
        )
        await self.nodes_service.update_many(
            query=QuerySpec(
                where=NodeClauseFactory.with_owner_id(from_user_id)
            ),
            builder=NodeBuilder(owner_id=to_user_id),
        )

    async def list_with_summary(
        self, page: int, size: int, query: QuerySpec
    ) -> ListResult[UserWithSummary]:
        return await self.repository.list_with_summary(
            page=page, size=size, query=query
        )

    async def complete_intro(self, user_id: int) -> UserProfile:
        builder = UserProfileBuilder(completed_intro=True)
        return await self.update_profile(user_id, builder)

    async def change_password(self, user_id: int, password: str) -> None:
        user = await self.get_by_id(user_id)
        if user is None:
            raise NotFoundException()
        if user.username in SYSTEM_USERS:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=PRECONDITION_FAILED,
                        message="Cannot change password for system users.",
                    )
                ]
            )
        user_profile = await self.get_user_profile(user.username)
        assert user_profile is not None
        if not user_profile.is_local:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=PRECONDITION_FAILED,
                        message="Cannot change password for external users.",
                    )
                ]
            )

        hashed_password = UserBuilder.hash_password(password)
        await self._update_resource(
            user, UserBuilder(password=hashed_password)
        )
