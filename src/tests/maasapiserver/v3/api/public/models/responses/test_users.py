#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.users import (
    UserResponse,
    UserWithSummaryResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.users import User, UserWithSummary
from maasservicelayer.utils.date import utcnow


class TestUserResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        user = User(
            id=1,
            username="test_username",
            password="test_password",
            is_superuser=False,
            first_name="test_first_name",
            last_name="test_last_name",
            is_staff=False,
            is_active=False,
            date_joined=now,
            email="email@example.com",
            last_login=now,
        )
        user_response = UserResponse.from_model(
            user, self_base_hyperlink=f"{V3_API_PREFIX}/users"
        )
        assert user_response.id == user.id
        assert user_response.username == user.username
        assert user_response.is_superuser == user.is_superuser
        assert user_response.first_name == user.first_name
        assert user_response.last_name == user.last_name
        assert user_response.date_joined == user.date_joined
        assert user_response.email == user.email
        assert user_response.last_login == user.last_login
        assert user_response.hal_links is not None
        assert (
            user_response.hal_links.self.href
            == f"{V3_API_PREFIX}/users/{user.id}"
        )


class TestUserWithSummaryResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        user = UserWithSummary(
            id=1,
            completed_intro=False,
            email="email@example.com",
            is_local=True,
            is_superuser=False,
            last_name="test_last_name",
            last_login=now,
            machines_count=10,
            sshkeys_count=20,
            username="test_username",
        )
        user_response = UserWithSummaryResponse.from_model(
            user, self_base_hyperlink=f"{V3_API_PREFIX}/users"
        )
        assert user_response.id == user.id
        assert user_response.completed_intro == user.completed_intro
        assert user_response.email == user.email
        assert user_response.is_local == user.is_local
        assert user_response.is_superuser == user.is_superuser
        assert user_response.is_superuser == user.is_superuser
        assert user_response.last_name == user.last_name
        assert user_response.last_login == user.last_login
        assert user_response.machines_count == user.machines_count
        assert user_response.sshkeys_count == user.sshkeys_count
        assert user_response.username == user.username
        assert user_response.hal_links is not None
        assert (
            user_response.hal_links.self.href
            == f"{V3_API_PREFIX}/users/{user.id}"
        )
