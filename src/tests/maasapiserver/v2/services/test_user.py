from datetime import datetime, timedelta

from django.core import signing
import pytest

from maasapiserver.v2.services.user import UserService


@pytest.mark.asyncio
class TestUserService:
    async def test_get_by_session_id_not_found(self, db_connection):
        service = UserService(db_connection)
        user = await service.get_by_session_id("a-b-c")
        assert user is None

    async def test_get_by_session_id_found(self, db_connection, fixture):
        [created_user] = await fixture.create(
            "auth_user",
            {
                "username": "user",
                "first_name": "User",
                "last_name": "One",
                "email": "user@example.com",
                "password": "secret",
                "is_active": True,
                "date_joined": datetime.utcnow(),
                "is_staff": False,
                "is_superuser": False,
            },
        )
        user_id = created_user["id"]
        session_id = "a-b-c"

        signer = signing.TimestampSigner(
            "<UNUSED>",
            salt="django.contrib.sessions.SessionStore",
            algorithm="sha256",
        )
        session_data = signer.sign_object(
            {
                "_auth_user_id": str(user_id),
            },
            serializer=signing.JSONSerializer,
        )
        await fixture.create(
            "django_session",
            {
                "session_key": session_id,
                "expire_date": datetime.utcnow() + timedelta(days=1),
                "session_data": session_data,
            },
        )
        service = UserService(db_connection)
        user = await service.get_by_session_id(session_id)
        assert user.id == user_id
