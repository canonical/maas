from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.users import UsersRepository
from maasapiserver.v3.services import UsersService


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestUsersService:
    async def test_get(self, db_connection: AsyncConnection) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_repository_mock.find_by_username = AsyncMock()
        users_service = UsersService(
            db_connection, users_repository=users_repository_mock
        )
        await users_service.get("test")
        users_repository_mock.find_by_username.assert_called_once_with("test")

    async def test_get_by_session_id(
        self, db_connection: AsyncConnection
    ) -> None:
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
