import pytest

from maasapiserver.v2.services.user import UserService
from tests.fixtures.factories.user import create_test_session, create_test_user


@pytest.mark.asyncio
class TestUserService:
    async def test_get_by_session_id_not_found(self, db_connection):
        service = UserService(db_connection)
        user = await service.get_by_session_id("a-b-c")
        assert user is None

    async def test_get_by_session_id_found(self, db_connection, fixture):
        user = await create_test_user(fixture)
        await create_test_session(
            fixture=fixture, user_id=user.id, session_id="test_session"
        )
        service = UserService(db_connection)
        retrieved_user = await service.get_by_session_id("test_session")
        assert retrieved_user.id == user.id
