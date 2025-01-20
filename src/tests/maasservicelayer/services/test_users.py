#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.users import UsersRepository
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.users import User, UserBuilder, UserProfileBuilder
from maasservicelayer.services import UsersService
from maasservicelayer.services._base import BaseService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonUsersService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return UsersService(
            context=Context(), users_repository=Mock(UsersRepository)
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        now = utcnow()
        return User(
            id=1,
            username="test_username",
            password="test_password",
            first_name="test_first_name",
            last_name="test_last_name",
            is_superuser=False,
            is_active=False,
            is_staff=False,
            email="email@example.com",
            date_joined=now,
            last_login=now,
        )


@pytest.mark.asyncio
class TestUsersService:
    async def test_get_by_session_id(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_service = UsersService(
            context=Context(), users_repository=users_repository_mock
        )
        await users_service.get_by_session_id(sessionid="sessionid")
        users_repository_mock.find_by_sessionid.assert_called_once_with(
            "sessionid"
        )

    async def test_get_user_profile(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_service = UsersService(
            context=Context(), users_repository=users_repository_mock
        )
        await users_service.get_user_profile(username="username")
        users_repository_mock.get_user_profile.assert_called_once_with(
            "username"
        )

    async def test_create_profile(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_service = UsersService(
            context=Context(), users_repository=users_repository_mock
        )
        builder = UserProfileBuilder(
            is_local=True, completed_intro=True, auth_last_check=utcnow()
        )
        await users_service.create_profile(user_id=1, builder=builder)
        users_repository_mock.create_profile.assert_called_once_with(
            user_id=1, builder=builder
        )

    async def test_update_profile(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_service = UsersService(
            context=Context(), users_repository=users_repository_mock
        )
        builder = UserProfileBuilder()
        builder.auth_last_check = utcnow()
        await users_service.update_profile(user_id=1, builder=builder)
        users_repository_mock.update_profile.assert_called_once_with(
            user_id=1, builder=builder
        )

    async def test_get_user_apikeys(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_service = UsersService(
            context=Context(), users_repository=users_repository_mock
        )
        await users_service.get_user_apikeys(username="username")
        users_repository_mock.get_user_apikeys.assert_called_once_with(
            "username"
        )

    async def test_create(self) -> None:
        now = utcnow()
        test_user = User(
            id=1,
            username="test_username",
            password="test_password",
            first_name="test_first_name",
            last_name="test_last_name",
            is_superuser=False,
            is_active=False,
            is_staff=False,
            email="email@example.com",
            date_joined=now,
            last_login=now,
        )

        blank_create_resource = UserBuilder()

        users_repository_mock = Mock(UsersRepository)
        users_repository_mock.create.return_value = test_user

        users_service = UsersService(
            context=Context(), users_repository=users_repository_mock
        )
        await users_service.create(blank_create_resource)

        users_repository_mock.create.assert_called_once()

        # Ensure a new user profile is created each time also
        users_repository_mock.create_profile.assert_called_once_with(
            user_id=1,
            builder=UserProfileBuilder(
                auth_last_check=None, is_local=True, completed_intro=False
            ),
        )
