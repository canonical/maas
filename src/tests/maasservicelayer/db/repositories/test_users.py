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
        now = utcnow()
        resource = (
            UserCreateOrUpdateResourceBuilder()
            .with_username("username")
            .with_first_name("first")
            .with_last_name("last")
            .with_email("test@example.com")
            .with_is_active(True)
            .with_is_staff(False)
            .with_is_superuser(False)
            .with_password("password")
            .with_date_joined(now)
            .with_last_login(now)
            .build()
        )

        assert resource.get_values() == {
            "username": "username",
            "first_name": "first",
            "last_name": "last",
            "email": "test@example.com",
            "is_active": True,
            "is_staff": False,
            "is_superuser": False,
            "password": "password",
            "date_joined": now,
            "last_login": now,
        }


class TestUserProfileCreateOrUpdateResourceBuilder:
    def test_builder(self) -> None:
        now = utcnow()
        resource = (
            UserProfileCreateOrUpdateResourceBuilder()
            .with_auth_last_check(now)
            .with_completed_intro(True)
            .with_is_local(False)
            .build()
        )
        assert resource.get_values() == {
            "auth_last_check": now,
            "completed_intro": True,
            "is_local": False,
        }


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
            expire_date=datetime.datetime.now(datetime.timezone.utc)
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

    async def test_create_user_profile(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        user = await create_test_user(fixture)
        users_repository = UsersRepository(db_connection)
        now = utcnow()
        user_profile_builder = (
            UserProfileCreateOrUpdateResourceBuilder()
            .with_is_local(True)
            .with_completed_intro(True)
            .with_auth_last_check(now)
        )
        user_profile = await users_repository.create_profile(
            user.id, user_profile_builder.build()
        )
        assert user_profile.is_local is True
        assert user_profile.completed_intro is True
        assert user_profile.auth_last_check == now

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
