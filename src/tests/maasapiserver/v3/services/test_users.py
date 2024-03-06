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
