# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import Mock

import pytest

from maascommon.enums.notifications import NotificationCategoryEnum
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.notifications import (
    NotificationsRepository,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    NotFoundException,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.models.notifications import Notification
from maasservicelayer.services.notifications import NotificationsService
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_NOTIFICATION = Notification(
    id=1,
    ident="deprecation_MD5_users",
    message="Foo is deprecated, please update",
    users=True,
    admins=False,
    context={},
    user_id=None,
    category=NotificationCategoryEnum.WARNING,
    dismissable=True,
)


@pytest.mark.asyncio
class TestCommonNotificationsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> NotificationsService:
        return NotificationsService(
            context=Context(), repository=Mock(NotificationsRepository)
        )

    @pytest.fixture
    def test_instance(self) -> Notification:
        return Notification(
            id=1,
            ident="deprecation_MD5_users",
            message="Foo is deprecated, please update",
            users=True,
            admins=False,
            context={},
            user_id=None,
            category=NotificationCategoryEnum.WARNING,
            dismissable=True,
        )


class TestNotificationsService:
    @pytest.fixture
    def notifications_repo_mock(self) -> Mock:
        return Mock(NotificationsRepository)

    @pytest.fixture
    def notifications_service(
        self, notifications_repo_mock: Mock
    ) -> NotificationsService:
        return NotificationsService(
            context=Context(), repository=notifications_repo_mock
        )

    @pytest.fixture
    def auth_user(self) -> AuthenticatedUser:
        return AuthenticatedUser(id=1, username="foo", roles={UserRole.USER})

    async def test_list_all_for_user(
        self,
        notifications_repo_mock: Mock,
        notifications_service: NotificationsService,
        auth_user: AuthenticatedUser,
    ) -> None:
        notifications_repo_mock.list_all_for_user.return_value = []
        await notifications_service.list_all_for_user(
            page=1, size=2, user=auth_user
        )
        notifications_repo_mock.list_all_for_user.assert_called_once_with(
            page=1, size=2, user_id=auth_user.id, is_admin=auth_user.is_admin()
        )

    async def test_list_active_for_user(
        self,
        notifications_repo_mock: Mock,
        notifications_service: NotificationsService,
        auth_user: AuthenticatedUser,
    ) -> None:
        notifications_repo_mock.list_active_for_user.return_value = []
        await notifications_service.list_active_for_user(
            page=1, size=2, user=auth_user
        )
        notifications_repo_mock.list_active_for_user.assert_called_once_with(
            page=1, size=2, user_id=auth_user.id, is_admin=auth_user.is_admin()
        )

    async def test_get_by_id_for_user(
        self,
        notifications_repo_mock: Mock,
        notifications_service: NotificationsService,
        auth_user: AuthenticatedUser,
    ) -> None:
        notifications_repo_mock.get_by_id_for_user.return_value = (
            TEST_NOTIFICATION
        )
        await notifications_service.get_by_id_for_user(
            notification_id=1, user=auth_user
        )
        notifications_repo_mock.get_by_id_for_user.assert_called_once_with(
            notification_id=1,
            user_id=auth_user.id,
            is_admin=auth_user.is_admin(),
        )

    async def test_dismiss(
        self,
        notifications_repo_mock: Mock,
        notifications_service: NotificationsService,
        auth_user: AuthenticatedUser,
    ) -> None:
        notifications_repo_mock.get_by_id_for_user.return_value = (
            TEST_NOTIFICATION
        )
        notifications_repo_mock.create_notification_dismissal.return_value = (
            None
        )
        await notifications_service.dismiss(notification_id=1, user=auth_user)
        notifications_repo_mock.create_notification_dismissal.assert_called_once_with(
            notification_id=1,
            user_id=auth_user.id,
        )

    async def test_dismiss_non_dismissable(
        self,
        notifications_repo_mock: Mock,
        notifications_service: NotificationsService,
        auth_user: AuthenticatedUser,
    ) -> None:
        non_dismissable_notification = TEST_NOTIFICATION
        non_dismissable_notification.dismissable = False
        notifications_repo_mock.get_by_id_for_user.return_value = (
            non_dismissable_notification
        )
        notifications_repo_mock.create_notification_dismissal.return_value = (
            None
        )
        with pytest.raises(BadRequestException):
            await notifications_service.dismiss(
                notification_id=1, user=auth_user
            )
        notifications_repo_mock.create_notification_dismissal.assert_not_called()

    async def test_dismiss_not_found(
        self,
        notifications_repo_mock: Mock,
        notifications_service: NotificationsService,
        auth_user: AuthenticatedUser,
    ) -> None:
        notifications_repo_mock.get_by_id_for_user.return_value = None
        with pytest.raises(NotFoundException):
            await notifications_service.dismiss(
                notification_id=1, user=auth_user
            )
        notifications_repo_mock.create_notification_dismissal.assert_not_called()
