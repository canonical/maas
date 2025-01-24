#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.users import UsersRepository
from maasservicelayer.models.users import UserBuilder, UserProfileBuilder
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.user import (
    create_test_session,
    create_test_user,
    create_test_user_consumer,
    create_test_user_profile,
    create_test_user_token,
)
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestUsersRepository:
    async def test_find_by_username(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        users_repository = UsersRepository(Context(connection=db_connection))
        assert (await users_repository.find_by_username("unexisting")) is None
        fetched_user = await users_repository.find_by_username(user.username)
        assert user == fetched_user

    async def test_find_by_session_id(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        await create_test_session(fixture, user.id, "test_session")

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
            "test_session",
            expire_date=datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(seconds=1),
        )

        users_repository = UsersRepository(Context(connection=db_connection))
        assert (
            await users_repository.find_by_sessionid("test_session")
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

    async def test_get_user_apikeys(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        user_consumer = await create_test_user_consumer(fixture, user.id)
        user_token = await create_test_user_token(
            fixture, user.id, user_consumer.id
        )

        apikey = ":".join(
            [user_consumer.key, user_token.key, user_token.secret]
        )

        users_repository = UsersRepository(Context(connection=db_connection))
        apikeys = await users_repository.get_user_apikeys(user.username)
        assert apikeys[0] == apikey

    async def test_delete_profile(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        user_profile = await create_test_user_profile(fixture, user.id)
        users_repository = UsersRepository(Context(connection=db_connection))
        deleted_user_profile = await users_repository.delete_profile(user.id)
        assert deleted_user_profile == user_profile

    async def test_delete_user_api_keys(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        user_consumer = await create_test_user_consumer(fixture, user.id)
        await create_test_user_token(fixture, user.id, user_consumer.id)
        users_repository = UsersRepository(Context(connection=db_connection))
        await users_repository.delete_user_api_keys(user.id)
        apikeys = await users_repository.get_user_apikeys(user.username)
        assert apikeys is None
