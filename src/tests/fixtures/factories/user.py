from datetime import datetime, timedelta
from typing import Any

from django.core import signing

from maasapiserver.common.utils.date import utcnow
from maasservicelayer.models.users import User, UserProfile
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_user(
    fixture: Fixture, **extra_details: dict[str, Any]
) -> User:
    date_joined = utcnow()

    user = {
        "username": "myusername",
        "password": "pbkdf2_sha256$260000$f1nMJPH4Z5Wc8QxkTsZ1p6$ylZBpgGE3FNlP2zOU21cYiLtvxwtkglsPKUETtXhzDw=",  # hash('test')
        "is_superuser": False,
        "first_name": "first",
        "last_name": "last",
        "is_staff": False,
        "is_active": True,
        "date_joined": date_joined,
    }
    user.update(extra_details)

    [created_user] = await fixture.create(
        "auth_user",
        [user],
    )
    return User(**created_user)


async def create_test_session(
    fixture: Fixture,
    user_id: int,
    session_id: str = "a-b-c",
    expire_date: datetime = utcnow() + timedelta(days=1),
) -> None:
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
            "expire_date": expire_date,
            "session_data": session_data,
        },
    )


async def create_test_user_profile(
    fixture: Fixture, user_id: int, **extra_details: dict[str, Any]
) -> UserProfile:
    user_profile = {
        "completed_intro": True,
        "auth_last_check": None,
        "is_local": False,
        "user_id": user_id,
    }

    user_profile.update(extra_details)
    [created_profile] = await fixture.create(
        "maasserver_userprofile", [user_profile]
    )
    return UserProfile(**created_profile)
