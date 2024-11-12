#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.users import (
    UserCreateOrUpdateResourceBuilder,
    UserProfileCreateOrUpdateResourceBuilder,
    UsersRepository,
)
from maasservicelayer.services import UsersService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestUsersService:
    async def test_get(self) -> None:
        db_connection = Mock(AsyncConnection)
        users_repository_mock = Mock(UsersRepository)
        users_repository_mock.find_by_username = AsyncMock()
        users_service = UsersService(
            db_connection, users_repository=users_repository_mock
        )
        await users_service.get("test")
        users_repository_mock.find_by_username.assert_called_once_with("test")

    async def test_get_by_session_id(self) -> None:
        db_connection = Mock(AsyncConnection)
        users_repository_mock = Mock(UsersRepository)
        users_repository_mock.find_by_sessionid = AsyncMock()
        users_service = UsersService(
            db_connection, users_repository=users_repository_mock
        )
        await users_service.get_by_session_id(sessionid="sessionid")
        users_repository_mock.find_by_sessionid.assert_called_once_with(
            "sessionid"
        )

    async def test_get_user_profile(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_repository_mock.get_user_profile = AsyncMock()
        users_service = UsersService(
            Mock(AsyncConnection), users_repository=users_repository_mock
        )
        await users_service.get_user_profile(username="username")
        users_repository_mock.get_user_profile.assert_called_once_with(
            "username"
        )

    async def test_update(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_repository_mock.update = AsyncMock()
        users_service = UsersService(
            Mock(AsyncConnection), users_repository=users_repository_mock
        )
        builder = UserCreateOrUpdateResourceBuilder()
        builder.with_last_name("test")
        await users_service.update(user_id=1, resource=builder.build())
        users_repository_mock.update.assert_called_once_with(
            id=1, resource=builder.build()
        )

    async def test_create_profile(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_repository_mock.create_profile = AsyncMock()
        users_service = UsersService(
            Mock(AsyncConnection), users_repository=users_repository_mock
        )
        builder = (
            UserProfileCreateOrUpdateResourceBuilder()
            .with_is_local(True)
            .with_completed_intro(True)
            .with_auth_last_check(utcnow())
        )
        await users_service.create_profile(user_id=1, resource=builder.build())
        users_repository_mock.create_profile.assert_called_once_with(
            user_id=1, resource=builder.build()
        )

    async def test_update_profile(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_repository_mock.update_profile = AsyncMock()
        users_service = UsersService(
            Mock(AsyncConnection), users_repository=users_repository_mock
        )
        builder = UserProfileCreateOrUpdateResourceBuilder()
        builder.with_auth_last_check(utcnow())
        await users_service.update_profile(user_id=1, resource=builder.build())
        users_repository_mock.update_profile.assert_called_once_with(
            user_id=1, resource=builder.build()
        )

    async def test_get_user_apikeys(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_repository_mock.get_user_apikeys = AsyncMock()
        users_service = UsersService(
            Mock(AsyncConnection), users_repository=users_repository_mock
        )
        await users_service.get_user_apikeys(username="username")
        users_repository_mock.get_user_apikeys.assert_called_once_with(
            "username"
        )
