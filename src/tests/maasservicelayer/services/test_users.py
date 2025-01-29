#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

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
    PreconditionFailedException,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.ipranges import IPRangeBuilder
from maasservicelayer.models.nodes import NodeBuilder
from maasservicelayer.models.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.models.users import User, UserBuilder, UserProfileBuilder
from maasservicelayer.services import UsersService
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
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

now = utcnow()
TEST_USER = User(
    id=1,
    username="test_username",
    password="test_password",
    first_name="test_first_name",
    last_name="test_last_name",
    is_superuser=False,
    is_active=False,
    is_staff=False,
    email="email@example.com",
    date_joined=now,
    last_login=now,
)


@pytest.mark.asyncio
class TestCommonUsersService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        service = UsersService(
            context=Context(),
            users_repository=Mock(UsersRepository),
            staticipaddress_service=Mock(StaticIPAddressService),
            ipranges_service=Mock(IPRangesService),
            nodes_service=Mock(NodesService),
            sshkey_service=Mock(SshKeysService),
            sslkey_service=Mock(SSLKeysService),
            notification_service=Mock(NotificationsService),
            notification_dismissal_service=Mock(NotificationDismissalService),
            filestorage_service=Mock(FileStorageService),
        )
        # we test the pre delete hook in the next tests
        service.pre_delete_hook = AsyncMock()
        return service

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return TEST_USER


@pytest.mark.asyncio
class TestUsersService:
    @pytest.fixture
    def users_repository(self) -> Mock:
        return Mock(UsersRepository)

    @pytest.fixture
    def users_service(self, users_repository: Mock):
        return UsersService(
            context=Context(),
            users_repository=users_repository,
            staticipaddress_service=Mock(StaticIPAddressService),
            ipranges_service=Mock(IPRangesService),
            nodes_service=Mock(NodesService),
            sshkey_service=Mock(SshKeysService),
            sslkey_service=Mock(SSLKeysService),
            notification_service=Mock(NotificationsService),
            notification_dismissal_service=Mock(NotificationDismissalService),
            filestorage_service=Mock(FileStorageService),
        )

    async def test_get_by_session_id(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        await users_service.get_by_session_id(sessionid="sessionid")
        users_repository.find_by_sessionid.assert_called_once_with("sessionid")

    async def test_get_user_profile(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        await users_service.get_user_profile(username="username")
        users_repository.get_user_profile.assert_called_once_with("username")

    async def test_create_profile(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        builder = UserProfileBuilder(
            is_local=True, completed_intro=True, auth_last_check=utcnow()
        )
        await users_service.create_profile(user_id=1, builder=builder)
        users_repository.create_profile.assert_called_once_with(
            user_id=1, builder=builder
        )

    async def test_update_profile(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        builder = UserProfileBuilder()
        builder.auth_last_check = utcnow()
        await users_service.update_profile(user_id=1, builder=builder)
        users_repository.update_profile.assert_called_once_with(
            user_id=1, builder=builder
        )

    async def test_delete_profile(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        builder = UserProfileBuilder()
        builder.auth_last_check = utcnow()
        await users_service.update_profile(user_id=1, builder=builder)
        users_repository.update_profile.assert_called_once_with(
            user_id=1, builder=builder
        )

    async def test_get_user_apikeys(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        await users_service.get_user_apikeys(username="username")
        users_repository.get_user_apikeys.assert_called_once_with("username")

    async def test_create(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:

        blank_create_resource = UserBuilder()

        users_repository.create.return_value = TEST_USER

        await users_service.create(blank_create_resource)

        users_repository.create.assert_called_once()

        # Ensure a new user profile is created each time also
        users_repository.create_profile.assert_called_once_with(
            user_id=1,
            builder=UserProfileBuilder(
                auth_last_check=None, is_local=True, completed_intro=False
            ),
        )

    @pytest.mark.parametrize(
        "resources, should_raise",
        [
            ({"ipaddr": False, "ipranges": False, "nodes": False}, False),
            (
                {
                    "ipaddr": True,
                    "ipranges": False,
                    "nodes": False,
                },
                True,
            ),
            ({"ipaddr": False, "ipranges": True, "nodes": False}, True),
            ({"ipaddr": False, "ipranges": False, "nodes": True}, True),
            (
                {
                    "ipaddr": True,
                    "ipranges": False,
                    "nodes": True,
                },
                True,
            ),
            (
                {
                    "ipaddr": True,
                    "ipranges": True,
                    "nodes": True,
                },
                True,
            ),
        ],
    )
    async def test_pre_delete_hook(
        self,
        users_service: UsersService,
        resources: dict[str, list],
        should_raise: bool,
    ) -> None:
        users_service.staticipaddress_service.exists.return_value = resources[
            "ipaddr"
        ]
        users_service.ipranges_service.exists.return_value = resources[
            "ipranges"
        ]
        users_service.nodes_service.exists.return_value = resources["nodes"]
        if should_raise:
            with pytest.raises(PreconditionFailedException):
                await users_service.pre_delete_hook(TEST_USER)

        else:
            await users_service.pre_delete_hook(TEST_USER)

    async def test_post_delete_hook(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:

        await users_service.post_delete_hook(TEST_USER)
        users_repository.delete_profile.assert_called_once_with(
            user_id=TEST_USER.id
        )
        users_repository.delete_user_api_keys.assert_called_once_with(
            TEST_USER.id
        )
        users_service.sshkey_service.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=SshKeyClauseFactory.with_user_id(TEST_USER.id)
            )
        )
        users_service.sslkey_service.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=SSLKeyClauseFactory.with_user_id(TEST_USER.id)
            )
        )
        users_service.notification_service.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=NotificationsClauseFactory.with_user_id(TEST_USER.id)
            )
        )
        users_service.notification_dismissal_service.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=NotificationDismissalsClauseFactory.with_user_id(
                    TEST_USER.id
                )
            )
        )
        users_service.filestorage_service.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=FileStorageClauseFactory.with_owner_id(TEST_USER.id)
            )
        )

    async def test_transfer_resources(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        user2 = TEST_USER.copy()
        user2.id = 2
        users_repository.get_by_id.return_value = user2

        await users_service.transfer_resources(TEST_USER.id, user2.id)
        users_service.staticipaddress_service.update_many.assert_called_once_with(
            query=QuerySpec(
                where=StaticIPAddressClauseFactory.with_user_id(TEST_USER.id)
            ),
            builder=StaticIPAddressBuilder(user_id=user2.id),
        )
        users_service.ipranges_service.update_many.assert_called_once_with(
            query=QuerySpec(
                where=IPRangeClauseFactory.with_user_id(TEST_USER.id)
            ),
            builder=IPRangeBuilder(user_id=user2.id),
        )
        users_service.nodes_service.update_many.assert_called_once_with(
            query=QuerySpec(
                where=NodeClauseFactory.with_owner_id(TEST_USER.id)
            ),
            builder=NodeBuilder(owner_id=user2.id),
        )

    async def test_transfer_resources_non_existent_user(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        users_repository.exists.return_value = False
        with pytest.raises(BadRequestException):
            await users_service.transfer_resources(1, 2)

    async def test_delete_user_apikeys(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        await users_service.delete_user_api_keys(1)
        users_repository.delete_user_api_keys.assert_called_once_with(1)
