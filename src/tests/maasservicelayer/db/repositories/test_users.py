#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import datetime
from typing import List

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.users import (
    UserCreateOrUpdateResourceBuilder,
    UserProfileCreateOrUpdateResourceBuilder,
    UsersRepository,
)
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.user import (
    create_test_session,
    create_test_user,
    create_test_user_consumer,
    create_test_user_profile,
    create_test_user_token,
)
from tests.maasapiserver.fixtures.db import Fixture


class TestUserCreateOrUpdateResourceBuilder:
    def test_builder(self) -> None:
        resource = (
            UserCreateOrUpdateResourceBuilder()
            .with_last_name("test")
            .with_email("test@example.com")
            .with_is_active(True)
            .with_is_superuser(False)
            .build()
        )

        assert resource.get_values() == {
            "last_name": "test",
            "email": "test@example.com",
            "is_active": True,
            "is_superuser": False,
        }


class TestUserProfileCreateOrUpdateResourceBuilder:
    def test_builder(self) -> None:
        now = utcnow()
        resource = (
            UserProfileCreateOrUpdateResourceBuilder()
            .with_auth_last_check(now)
            .build()
        )
        assert resource.get_values() == {"auth_last_check": now}


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestUsersRepository:
    async def test_find_by_username(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        users_repository = UsersRepository(db_connection)
        assert (await users_repository.find_by_username("unexisting")) is None
        fetched_user = await users_repository.find_by_username(user.username)
        assert user == fetched_user

    async def test_find_by_session_id(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        await create_test_session(fixture, user.id, "test_session")

        users_repository = UsersRepository(db_connection)
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
            expire_date=datetime.datetime.utcnow()
            - datetime.timedelta(seconds=1),
        )

        users_repository = UsersRepository(db_connection)
        assert (
            await users_repository.find_by_sessionid("test_session")
        ) is None

    async def test_get_user_profile(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        user_profile = await create_test_user_profile(fixture, user.id)
        users_repository = UsersRepository(db_connection)
        assert (
            await users_repository.get_user_profile(user.username)
        ) == user_profile

    async def test_update(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        users_repository = UsersRepository(db_connection)
        builder = UserCreateOrUpdateResourceBuilder()
        builder.with_last_name("test")
        updated_user = await users_repository.update(user.id, builder.build())
        assert updated_user.last_name == "test"

    async def test_update_profile(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        now = utcnow()
        user = await create_test_user(fixture)
        await create_test_user_profile(fixture, user.id)
        users_repository = UsersRepository(db_connection)
        builder = UserProfileCreateOrUpdateResourceBuilder()
        builder.with_auth_last_check(now)
        updated_profile = await users_repository.update_profile(
            user.id, builder.build()
        )
        assert updated_profile.auth_last_check == now

    async def test_get_user_apikeys(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> List[str]:
        user = await create_test_user(fixture)
        user_consumer = await create_test_user_consumer(fixture, user.id)
        user_token = await create_test_user_token(
            fixture, user.id, user_consumer.id
        )

        apikey = ":".join(
            [user_consumer.key, user_token.key, user_token.secret]
        )

        users_repository = UsersRepository(db_connection)
        apikeys = await users_repository.get_user_apikeys(user.username)
        assert apikeys[0] == apikey
