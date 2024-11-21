#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.users import (
    UserProfileResourceBuilder,
    UserResourceBuilder,
    UsersRepository,
)
from maasservicelayer.services import UsersService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestUsersService:
    async def test_get(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_service = UsersService(
            context=Context(), users_repository=users_repository_mock
        )
        await users_service.get("test")
        users_repository_mock.find_by_username.assert_called_once_with("test")

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

    async def test_update(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_service = UsersService(
            context=Context(), users_repository=users_repository_mock
        )
        builder = UserResourceBuilder()
        builder.with_last_name("test")
        await users_service.update_by_id(user_id=1, resource=builder.build())
        users_repository_mock.update_by_id.assert_called_once_with(
            id=1, resource=builder.build()
        )

    async def test_create_profile(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_service = UsersService(
            context=Context(), users_repository=users_repository_mock
        )
        builder = (
            UserProfileResourceBuilder()
            .with_is_local(True)
            .with_completed_intro(True)
            .with_auth_last_check(utcnow())
        )
        await users_service.create_profile(user_id=1, resource=builder.build())
        users_repository_mock.create_profile.assert_called_once_with(
            user_id=1, resource=builder.build()
        )

    async def test_update_profile(self) -> None:
        users_repository_mock = Mock(UsersRepository)
        users_service = UsersService(
            context=Context(), users_repository=users_repository_mock
        )
        builder = UserProfileResourceBuilder()
        builder.with_auth_last_check(utcnow())
        await users_service.update_profile(user_id=1, resource=builder.build())
        users_repository_mock.update_profile.assert_called_once_with(
            user_id=1, resource=builder.build()
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
