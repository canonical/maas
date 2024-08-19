import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.users import UsersRepository
from tests.fixtures.factories.user import (
    create_test_session,
    create_test_user,
    create_test_user_profile,
)
from tests.maasapiserver.fixtures.db import Fixture


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
