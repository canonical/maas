from datetime import datetime, timedelta
from typing import Any

from django.core import signing

from maasservicelayer.models.users import Consumer, Token, User, UserProfile
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_user(fixture: Fixture, **extra_details: Any) -> User:
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
        key="<UNUSED>",
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
    fixture: Fixture, user_id: int, **extra_details: Any
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


async def create_test_user_consumer(
    fixture: Fixture, user_id: int, **extra_details: Any
) -> Consumer:
    consumer = {
        "name": "myconsumername",
        "description": "myconsumerdescription",
        "key": "cqJF8TCX9gZw8SZpNr",
        "secret": "",
        "status": "accepted",
        "user_id": user_id,
    }

    consumer.update(extra_details)
    [created_consumer] = await fixture.create("piston3_consumer", [consumer])
    return Consumer(**created_consumer)


async def create_test_user_token(
    fixture: Fixture, user_id: int, consumer_id: int, **extra_details: Any
) -> Token:
    token = {
        "key": "CtE9Cmy4asnRBtJvxQ",
        "secret": "DNPJDVa87vEesHE8sQ722yP6JJKnrem2",
        "verifier": "",
        "token_type": 2,
        "timestamp": 1725122700,
        "is_approved": True,
        "callback_confirmed": False,
        "consumer_id": consumer_id,
        "user_id": user_id,
    }

    [created_token] = await fixture.create("piston3_token", [token])
    return Token(**created_token)
