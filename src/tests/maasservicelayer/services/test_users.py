# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import time
from unittest.mock import AsyncMock, Mock

import pytest

from maascommon.enums.consumer import ConsumerState
from maascommon.enums.token import TokenType
from maasservicelayer.builders.consumers import ConsumerBuilder
from maasservicelayer.builders.ipranges import IPRangeBuilder
from maasservicelayer.builders.nodes import NodeBuilder
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.builders.tokens import TokenBuilder
from maasservicelayer.builders.users import UserBuilder, UserProfileBuilder
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
from maasservicelayer.db.repositories.tokens import TokenClauseFactory
from maasservicelayer.db.repositories.users import (
    UserClauseFactory,
    UsersRepository,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.consumers import Consumer
from maasservicelayer.models.tokens import Token
from maasservicelayer.models.users import User, UserProfile
from maasservicelayer.services import (
    ConsumersService,
    ServiceCollectionV3,
    TokensService,
    UsersService,
)
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.filestorage import FileStorageService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.notifications import NotificationsService
from maasservicelayer.services.sshkeys import SshKeysService
from maasservicelayer.services.sslkey import SSLKeysService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
import maasservicelayer.services.users as users_module
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.consumer import create_test_user_consumer
from tests.fixtures.factories.notifications import (
    create_test_notification_dismissal_entry,
    create_test_notification_entry,
)
from tests.fixtures.factories.sslkey import create_test_sslkey
from tests.fixtures.factories.token import create_test_user_token
from tests.fixtures.factories.user import (
    create_test_user,
    create_test_user_profile,
)
from tests.maasapiserver.fixtures.db import Fixture
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

TEST_USER_PROFILE = UserProfile(
    id=1, completed_intro=True, auth_last_check=None, is_local=True, user_id=1
)


@pytest.mark.asyncio
class TestIntegrationUserService:
    async def test_get_MAAS_user_apikey_creates_new_token(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        token = await services.users.get_MAAS_user_apikey()

        user_created = await services.users.repository.get_one(
            query=QuerySpec(where=UserClauseFactory.with_username("MAAS"))
        )
        assert user_created is not None

        consumer_created = await services.consumers.get_one(
            query=QuerySpec(
                where=ConsumerClauseFactory.with_user_id(user_created.id)
            )
        )
        assert consumer_created is not None
        token_created = await services.tokens.get_one(
            query=QuerySpec(
                where=TokenClauseFactory.with_consumer_id(consumer_created.id)
            )
        )
        assert token_created is not None
        assert token == ":".join(
            [consumer_created.key, token_created.key, token_created.secret]
        )

    async def test_get_MAAS_user_apikey_returns_existing_tokens(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        user = await create_test_user(fixture, username="MAAS")
        consumer = await create_test_user_consumer(fixture, user_id=user.id)
        token = await create_test_user_token(
            fixture, user_id=user.id, consumer_id=consumer.id
        )

        retrieved_token = await services.users.get_MAAS_user_apikey()
        assert retrieved_token == ":".join(
            [consumer.key, token.key, token.secret]
        )

    async def test_delete_cascade_entities(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        user = await create_test_user(fixture, username="foo")
        await create_test_user_profile(fixture, user_id=user.id)
        consumer = await create_test_user_consumer(fixture, user_id=user.id)
        await create_test_user_token(
            fixture, user_id=user.id, consumer_id=consumer.id
        )
        await create_test_sslkey(fixture, user_id=user.id)
        notification = await create_test_notification_entry(
            fixture, user_id=user.id
        )
        await create_test_notification_dismissal_entry(
            fixture, notification_id=notification.id, user_id=user.id
        )

        await services.users.delete_by_id(user.id)

        users = await services.users.get_many(query=QuerySpec())
        assert users == []
        profile = await services.users.get_user_profile("foo")
        assert profile is None
        consumers = await services.consumers.get_many(query=QuerySpec())
        assert consumers == []
        tokens = await services.tokens.get_many(query=QuerySpec())
        assert tokens == []
        sslkeys = await services.sslkeys.get_many(query=QuerySpec())
        assert sslkeys == []
        notifications = await services.notifications.get_many(
            query=QuerySpec()
        )
        assert notifications == []


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
            filestorage_service=Mock(FileStorageService),
            consumers_service=Mock(ConsumersService),
            tokens_service=Mock(TokensService),
        )
        # we test the pre delete hook in the next tests
        service.pre_delete_hook = AsyncMock()
        return service

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return TEST_USER

    @pytest.mark.skip("Not implemented yet")
    async def test_delete_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        await super().test_delete_many(service_instance, test_instance)


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
            filestorage_service=Mock(FileStorageService),
            consumers_service=Mock(ConsumersService),
            tokens_service=Mock(TokensService),
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

    async def test_get_or_create_MAAS_user_already_exists(
        self, users_service: UsersService, users_repository: Mock
    ):
        users_repository.get_one.return_value = TEST_USER
        user = await users_service.get_or_create_MAAS_user()
        assert user == TEST_USER
        users_repository.get_one.assert_called_once()
        users_repository.create.assert_not_called()
        users_repository.create_profile.assert_not_called()

    async def test_get_or_create_MAAS_user_is_created(
        self, users_service: UsersService, users_repository: Mock
    ):
        users_repository.get_one.return_value = None
        users_repository.create.return_value = TEST_USER
        user = await users_service.get_or_create_MAAS_user()
        assert user == TEST_USER
        users_repository.get_one.assert_called_once()
        users_repository.create.assert_called_once()
        users_repository.create_profile.assert_not_called()

    async def test_get_MAAS_user_apikey_already_exists(
        self, users_service: UsersService, users_repository: Mock
    ):
        # Mock MAAS user already exists
        users_repository.get_one.return_value = TEST_USER
        users_service.tokens_service.get_user_apikeys.return_value = [
            "my:api:key"
        ]
        token = await users_service.get_MAAS_user_apikey()
        assert token == "my:api:key"

    async def test_get_MAAS_user_apikey_is_created(
        self, users_service: UsersService, users_repository: Mock, mocker
    ):
        # Mock MAAS user already exists
        users_repository.get_one.return_value = TEST_USER
        mocker.patch.object(users_module, "get_random_string").side_effect = [
            "first",
            "second",
            "third",
        ]
        mocker.patch.object(
            users_module, "time"
        ).return_value = 1746224586.1421623
        users_service.tokens_service.get_user_apikeys.return_value = []
        consumer = Consumer(
            id=0,
            user_id=TEST_USER.id,
            name="MAAS consumer",
            description="",
            status=ConsumerState.ACCEPTED,
            key="consumer",
            secret="",
        )

        users_service.consumers_service.create.return_value = consumer

        token = Token(
            id=0,
            user_id=TEST_USER.id,
            token_type=TokenType.ACCESS,
            consumer_id=consumer.id,
            is_approved=True,
            key="key",
            secret="secret",
            timestamp=int(time.time()),
            callback_confirmed=False,
            verifier="",
        )
        users_service.tokens_service.create.return_value = token
        token = await users_service.get_MAAS_user_apikey()
        assert token == "consumer:key:secret"
        users_service.consumers_service.create.assert_called_once_with(
            ConsumerBuilder(
                user_id=TEST_USER.id,
                name="MAAS consumer",
                description="",
                status=ConsumerState.ACCEPTED,
                key="first",
                secret="",
            )
        )
        users_service.tokens_service.create.assert_called_once_with(
            TokenBuilder(
                user_id=TEST_USER.id,
                token_type=TokenType.ACCESS,
                consumer_id=consumer.id,
                is_approved=True,
                key="second",
                secret="third",
                verifier="",
                timestamp=1746224586,
                callback_confirmed=False,
            )
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
        users_service.consumers_service.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=ConsumerClauseFactory.with_user_id(TEST_USER.id)
            )
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

    async def test_list_with_summary(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        await users_service.list_with_summary(
            page=1, size=1000, query=QuerySpec(where=None)
        )
        users_repository.list_with_summary.assert_called_once_with(
            page=1, size=1000, query=QuerySpec(where=None)
        )

    async def test_complete_intro(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        users_repository.update_profile.return_value = TEST_USER_PROFILE
        await users_service.complete_intro(user_id=1)

        users_repository.update_profile.assert_called_once_with(
            user_id=1, builder=UserProfileBuilder(completed_intro=True)
        )

    async def test_change_password(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        users_repository.get_by_id.return_value = TEST_USER
        users_repository.get_user_profile.return_value = TEST_USER_PROFILE
        users_repository.update_by_id.return_value = TEST_USER
        await users_service.change_password(TEST_USER.id, "foo")

        users_repository.get_by_id.assert_called_once_with(id=TEST_USER.id)
        users_repository.get_user_profile.assert_called_once_with(
            TEST_USER.username
        )

        # we cannot assert with which parameters the method has been called
        # with because of the salt.
        users_repository.update_by_id.assert_called_once()

    async def test_change_password_system_user(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        system_user = TEST_USER.copy()
        system_user.username = "maas-init-node"
        users_repository.get_by_id.return_value = system_user

        with pytest.raises(BadRequestException) as exc:
            await users_service.change_password(TEST_USER.id, "foo")

        assert (
            exc.value.details[0].message
            == "Cannot change password for system users."
        )

    async def test_change_password_external_user(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        external_user_profile = TEST_USER_PROFILE.copy()
        external_user_profile.is_local = False
        users_repository.get_by_id.return_value = TEST_USER
        users_repository.get_user_profile.return_value = external_user_profile

        with pytest.raises(BadRequestException) as exc:
            await users_service.change_password(TEST_USER.id, "foo")

        assert (
            exc.value.details[0].message
            == "Cannot change password for external users."
        )

    async def test_change_password_not_found(
        self, users_service: UsersService, users_repository: Mock
    ) -> None:
        users_repository.get_by_id.return_value = None

        with pytest.raises(NotFoundException):
            await users_service.change_password(TEST_USER.id, "foo")
