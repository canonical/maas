# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.users import UserBuilder, UserProfileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.users import (
    UserClauseFactory,
    UsersRepository,
)
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.node import (
    create_test_device_entry,
    create_test_machine_entry,
    create_test_rack_and_region_controller_entry,
)
from tests.fixtures.factories.token import create_test_refresh_token
from tests.fixtures.factories.user import (
    create_test_session,
    create_test_user,
    create_test_user_profile,
    create_test_user_sshkey,
)
from tests.maasapiserver.fixtures.db import Fixture


class TestUserClauseFactory:
    def test_builder(self) -> None:
        clause = UserClauseFactory.with_username_or_email_like(
            username_or_email_like="foo"
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == (
            "lower(auth_user.username) LIKE lower('%foo%') OR lower(auth_user.email) LIKE lower('%foo%')"
        )

    def test_with_ids(self):
        clause = UserClauseFactory.with_ids([1, 2])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_user.id IN (1, 2)"
        )


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestUsersRepository:
    async def test_find_by_session_id(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        await create_test_session(fixture, user.id, "abc123", "test_session")

        users_repository = UsersRepository(Context(connection=db_connection))
        assert (await users_repository.find_by_sessionid("unexisting")) is None

        fetched_user = await users_repository.find_by_sessionid("test_session")
        assert user == fetched_user

    async def test_find_by_session_id_expired(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        await create_test_session(
            fixture,
            user.id,
            "abc123",
            "test_session",
            expire_date=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(seconds=1),
        )

        users_repository = UsersRepository(Context(connection=db_connection))
        assert (
            await users_repository.find_by_sessionid("test_session")
        ) is None

    async def test_find_by_refresh_token(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        await create_test_refresh_token(
            fixture=fixture,
            user_id=user.id,
            token="test_refresh_token",
            expires_at=utcnow() + datetime.timedelta(hours=1),
        )

        users_repository = UsersRepository(Context(connection=db_connection))

        fetched_user = await users_repository.find_by_refresh_token(
            "test_refresh_token"
        )
        assert user == fetched_user

    async def test_find_by_refresh_token_expired(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        await create_test_refresh_token(
            fixture=fixture,
            user_id=user.id,
            token="test_refresh_token",
            expires_at=utcnow() - datetime.timedelta(hours=1),
        )

        users_repository = UsersRepository(Context(connection=db_connection))
        fetched_user = await users_repository.find_by_refresh_token(
            "test_refresh_token"
        )
        assert (fetched_user) is None

    async def test_clear_all_sessions(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        await create_test_session(fixture, user.id, "abc123", "test_session")
        await create_test_session(fixture, user.id, "abc123", "test_session2")

        users_repository = UsersRepository(Context(connection=db_connection))
        await users_repository.clear_all_sessions()
        assert (
            await users_repository.find_by_sessionid("test_session")
        ) is None
        assert (
            await users_repository.find_by_sessionid("test_session2")
        ) is None

    async def test_get_user_profile(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        user_profile = await create_test_user_profile(fixture, user.id)
        users_repository = UsersRepository(Context(connection=db_connection))
        assert (
            await users_repository.get_user_profile(user.username)
        ) == user_profile

    async def test_create_user_profile(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        users_repository = UsersRepository(Context(connection=db_connection))
        now = utcnow()
        user_profile_builder = UserProfileBuilder(
            is_local=True, completed_intro=True, auth_last_check=now
        )
        user_profile = await users_repository.create_profile(
            user.id, user_profile_builder
        )
        assert user_profile.is_local is True
        assert user_profile.completed_intro is True
        assert user_profile.auth_last_check == now

    async def test_update(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        users_repository = UsersRepository(Context(connection=db_connection))
        builder = UserBuilder(last_name="test")
        updated_user = await users_repository.update_by_id(user.id, builder)
        assert updated_user.last_name == "test"

    async def test_update_profile(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = utcnow()
        user = await create_test_user(fixture)
        await create_test_user_profile(fixture, user.id)
        users_repository = UsersRepository(Context(connection=db_connection))
        builder = UserProfileBuilder(auth_last_check=now)
        updated_profile = await users_repository.update_profile(
            user.id, builder
        )
        assert updated_profile.auth_last_check == now

    async def test_delete_profile(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        user_profile = await create_test_user_profile(fixture, user.id)
        users_repository = UsersRepository(Context(connection=db_connection))
        deleted_user_profile = await users_repository.delete_profile(user.id)
        assert deleted_user_profile == user_profile

    async def test_list(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_user(fixture, username="user1")
        await create_test_user(fixture, username="user2")
        users_repository = UsersRepository(Context(connection=db_connection))
        users_list = await users_repository.list(page=1, size=1000)
        assert users_list.total == 2
        assert len(users_list.items) == 2

    async def test_list_special_users(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_user(fixture, username="MAAS")
        await create_test_user(fixture, username="maas-init-node")

        users_repository = UsersRepository(Context(connection=db_connection))
        users_list = await users_repository.list(page=1, size=1000)
        assert users_list.total == 0
        assert users_list.items == []

    async def test_list_statistics(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user1 = await create_test_user(
            fixture, username="user1", is_active=True
        )
        await create_test_user_profile(fixture, user_id=user1.id)
        await create_test_machine_entry(fixture, owner_id=user1.id)
        await create_test_device_entry(fixture, owner_id=user1.id)
        await create_test_rack_and_region_controller_entry(
            fixture, owner_id=user1.id
        )

        user2 = await create_test_user(
            fixture, username="user2", is_active=True
        )
        await create_test_user_profile(fixture, user_id=user2.id)
        await create_test_machine_entry(fixture, owner_id=user2.id)
        await create_test_user_sshkey(fixture, key="foo", user_id=user2.id)
        await create_test_user_sshkey(fixture, key="foo", user_id=user2.id)

        user3 = await create_test_user(
            fixture, username="user3", is_active=True
        )
        await create_test_user_profile(fixture, user_id=user3.id)

        user4 = await create_test_user(
            fixture, username="user4", is_active=False
        )
        await create_test_user_profile(fixture, user_id=user4.id)

        users_repository = UsersRepository(Context(connection=db_connection))
        users_list = await users_repository.list_statistics(
            page=1, size=1000, query=QuerySpec(where=None)
        )
        # only active users should be listed
        assert users_list.total == 3
        # the list is sorted on the user id in descending order
        assert users_list.items[0].machines_count == 0
        assert users_list.items[0].sshkeys_count == 0
        assert users_list.items[1].machines_count == 1
        assert users_list.items[1].sshkeys_count == 2
        assert users_list.items[2].machines_count == 3
        assert users_list.items[2].sshkeys_count == 0

    async def test_list_statistics_special_users(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_user(fixture, username="MAAS")
        await create_test_user(fixture, username="maas-init-node")

        users_repository = UsersRepository(Context(connection=db_connection))
        users_list = await users_repository.list_statistics(
            page=1, size=1000, query=QuerySpec(where=None)
        )
        assert users_list.total == 0
        assert users_list.items == []

    @pytest.mark.parametrize(
        ("query", "num_results"),
        [
            ("no_match", 0),
            ("foo", 2),
            ("fOO", 2),
            ("bar", 1),
            ("example", 3),
        ],
    )
    async def test_list_statistics_filters(
        self,
        db_connection: AsyncConnection,
        fixture: Fixture,
        query: str,
        num_results: int,
    ) -> None:
        await create_test_user(
            fixture, username="foo", email="foo@example.com"
        )
        await create_test_user(
            fixture, username="FOOOOO!", email="hello@example.com"
        )
        await create_test_user(
            fixture, username="bar!", email="bar@example.com"
        )

        users_repository = UsersRepository(Context(connection=db_connection))
        users_list = await users_repository.list_statistics(
            page=1,
            size=1000,
            query=QuerySpec(
                where=UserClauseFactory.with_username_or_email_like(query)
            ),
        )
        assert users_list.total == num_results

    async def test_list_statistics_filter_by_ids(
        self,
        db_connection: AsyncConnection,
        fixture: Fixture,
        num_results: int,
    ) -> None:
        user1 = await create_test_user(
            fixture, username="johnmarston", email="foo@example.com"
        )
        user2 = await create_test_user(
            fixture, username="arthurmorgan", email="hello@example.com"
        )
        user3 = await create_test_user(
            fixture, username="hoseamatthews", email="bar@example.com"
        )

        users_repository = UsersRepository(Context(connection=db_connection))

        query = QuerySpec(
            where=UserClauseFactory.with_ids([user1.id, user3.id])
        )

        users_statistics = await users_repository.list_statistics(
            page=1,
            size=1000,
            query=query,
        )

        assert len(users_statistics.items) == 2
        assert users_statistics.total == 2
        assert users_statistics.items[0].id == user1.id
        assert users_statistics.items[1].id == user3.id

        query = QuerySpec(
            where=UserClauseFactory.with_ids([user1.id, user2.id, user3.id])
        )

        users_statistics = await users_repository.list_statistics(
            page=1,
            size=1000,
            query=query,
        )

        assert len(users_statistics.items) == 2
        assert users_statistics.total == 2

    async def test_get_by_id_statistics(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture, username="user", is_active=True)
        await create_test_user_profile(fixture, user_id=user.id)
        await create_test_machine_entry(fixture, owner_id=user.id)
        await create_test_user_sshkey(fixture, key="foo", user_id=user.id)
        await create_test_user_sshkey(fixture, key="bar", user_id=user.id)
        users_repository = UsersRepository(Context(connection=db_connection))

        user_statistics = await users_repository.get_by_id_statistics(user.id)
        assert user_statistics
        assert user_statistics.machines_count == 1
        assert user_statistics.sshkeys_count == 2

    async def test_get_by_id_statistics_system_user(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture, username="MAAS")
        users_repository = UsersRepository(Context(connection=db_connection))

        user_statistics = await users_repository.get_by_id_statistics(user.id)
        assert user_statistics is None

    async def test_count_by_provider(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user1 = await create_test_user(fixture, username="user1")
        user2 = await create_test_user(fixture, username="user2")
        user3 = await create_test_user(fixture, username="user3")

        provider1_id = 1
        provider2_id = 2

        await create_test_user_profile(
            fixture, user_id=user1.id, provider_id=provider1_id
        )
        await create_test_user_profile(
            fixture, user_id=user2.id, provider_id=provider1_id
        )
        await create_test_user_profile(
            fixture, user_id=user3.id, provider_id=provider2_id
        )

        users_repository = UsersRepository(Context(connection=db_connection))

        count_provider1 = await users_repository.count_by_provider(
            provider1_id
        )
        count_provider2 = await users_repository.count_by_provider(
            provider2_id
        )

        assert count_provider1 == 2
        assert count_provider2 == 1

    async def test_has_users(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_user(fixture, username="MAAS")
        users_repository = UsersRepository(Context(connection=db_connection))

        has_users = await users_repository.has_users()
        assert has_users is False

        await create_test_user(fixture, username="regular_user")

        has_users = await users_repository.has_users()
        assert has_users is True
