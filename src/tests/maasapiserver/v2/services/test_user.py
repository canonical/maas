import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v2.services.user import UserService
from maasservicelayer.context import Context
from tests.fixtures.factories.user import create_test_session, create_test_user
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestUserService:
    async def test_get_by_session_id_not_found(
        self, db_connection: AsyncConnection
    ):
        context = Context(connection=db_connection)
        service = UserService(context)
        user = await service.get_by_session_id("a-b-c")
        assert user is None

    async def test_get_by_session_id_found(
        self, db_connection: AsyncConnection, fixture: Fixture
    ):
        user = await create_test_user(fixture)
        await create_test_session(
            fixture=fixture, user_id=user.id, session_id="test_session"
        )
        context = Context(connection=db_connection)
        service = UserService(context)
        retrieved_user = await service.get_by_session_id("test_session")
        assert retrieved_user.id == user.id
