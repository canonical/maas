#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.filestorage import (
    FileStorageClauseFactory,
)
from maasservicelayer.db.repositories.ipranges import IPRangeClauseFactory
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.db.repositories.notification_dismissal import (
    NotificationDismissalsClauseFactory,
)
from maasservicelayer.db.repositories.notifications import (
    NotificationsClauseFactory,
)
from maasservicelayer.db.repositories.sshkeys import SshKeyClauseFactory
from maasservicelayer.db.repositories.sslkeys import SSLKeyClauseFactory
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.db.repositories.users import UsersRepository
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
    PRECONDITION_FAILED,
)
from maasservicelayer.models.ipranges import IPRangeBuilder
from maasservicelayer.models.nodes import NodeBuilder
from maasservicelayer.models.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.models.users import (
    User,
    UserBuilder,
    UserProfile,
    UserProfileBuilder,
)
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.filestorage import FileStorageService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.notification_dismissal import (
    NotificationDismissalService,
)
from maasservicelayer.services.notifications import NotificationsService
from maasservicelayer.services.sshkeys import SshKeysService
from maasservicelayer.services.sslkey import SSLKeysService
from maasservicelayer.services.staticipaddress import StaticIPAddressService


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
        notification_dismissal_service: NotificationDismissalService,
        filestorage_service: FileStorageService,
    ):
        super().__init__(context, users_repository)
        self.staticipaddress_service = staticipaddress_service
        self.ipranges_service = ipranges_service
        self.nodes_service = nodes_service
        self.sshkey_service = sshkey_service
        self.sslkey_service = sslkey_service
        self.notification_service = notification_service
        self.notification_dismissal_service = notification_dismissal_service
        self.filestorage_service = filestorage_service

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

    async def delete_profile(self, user_id: int) -> UserProfile:
        return await self.repository.delete_profile(user_id=user_id)

    async def delete_user_api_keys(self, user_id: int) -> None:
        return await self.repository.delete_user_api_keys(user_id)

    async def pre_delete_hook(self, resource_to_be_deleted: User) -> None:
        # TODO: switch to exists() query when we implement it
        owned_ipranges = await self.ipranges_service.get_ipranges_for_user(
            resource_to_be_deleted.id
        )
        owned_staticips = (
            await self.staticipaddress_service.get_staticips_for_user(
                resource_to_be_deleted.id
            )
        )
        owned_nodes = await self.nodes_service.get_nodes_for_user(
            resource_to_be_deleted.id
        )

        owned_resources = {
            "static IP address(es)": owned_staticips,
            "IP range(s)": owned_ipranges,
            "node(s)": owned_nodes,
        }
        if any(owned_resources.values()):
            details = [
                BaseExceptionDetail(
                    type=PRECONDITION_FAILED,
                    message=f"Cannot delete user. {len(resources)} {name} are still allocated.",
                )
                for name, resources in owned_resources.items()
                if len(resources) > 0
            ]
            raise PreconditionFailedException(details=details)

    async def post_delete_hook(self, resource: User) -> None:
        await self.delete_profile(resource.id)
        await self.delete_user_api_keys(resource.id)
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
        await self.notification_dismissal_service.delete_many(
            query=QuerySpec(
                where=NotificationDismissalsClauseFactory.with_user_id(
                    resource.id
                )
            )
        )
        await self.filestorage_service.delete_many(
            query=QuerySpec(
                where=FileStorageClauseFactory.with_owner_id(resource.id)
            )
        )

    async def transfer_resources(
        self, from_user_id: int, to_user_id: int
    ) -> None:
        to_user = await self.get_by_id(to_user_id)
        if not to_user:
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
