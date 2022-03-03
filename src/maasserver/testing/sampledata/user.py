from typing import List

from django.contrib.auth.models import User

from .common import range_one


def make_users(admin_count: int, user_count: int) -> List[User]:
    admins = [
        User.objects.create_superuser(
            f"admin{n}",
            email=f"admin{n}@example.com",
            password="secret",
        )
        for n in range_one(admin_count)
    ]
    users = [
        User.objects.create_user(
            f"user{n}",
            email=f"user{n}@example.com",
            password="secret",
        )
        for n in range_one(user_count)
    ]
    return admins + users
