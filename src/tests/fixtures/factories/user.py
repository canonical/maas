from datetime import datetime
from typing import Any

from maasapiserver.v3.models.users import User
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_user(
    fixture: Fixture, **extra_details: dict[str, Any]
) -> User:
    date_joined = datetime.utcnow().astimezone()

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
