# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.notifications import NotificationCategoryEnum
from maasservicelayer.builders.notifications import NotificationBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.notifications import (
    NotificationsClauseFactory,
    NotificationsRepository,
)
from maasservicelayer.db.tables import NotificationDismissalTable
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.notifications import (
    Notification,
    NotificationDismissal,
)
from maasservicelayer.models.users import User
from tests.fixtures.factories.notifications import (
    create_test_notification_dismissal_entry,
    create_test_notification_entry,
)
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestNotificationClauseFactory:
    def test_with_user_id(self) -> None:
        clause = NotificationsClauseFactory.with_user_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_notification.user_id = 1"
        )


class TestCommonNotificationRepository(RepositoryCommonTests[Notification]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> NotificationsRepository:
        return NotificationsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Notification]:
        notifications = []
        for i in range(num_objects):
            notifications.append(
                await create_test_notification_entry(fixture, ident=str(i))
            )
        return notifications

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> ResourceBuilder:
        return NotificationBuilder(
            ident="deprecation_MD5_users",
            message="Foo is deprecated, please update",
            users=True,
            admins=False,
            context={},
            user_id=None,
            category=NotificationCategoryEnum.WARNING,
            dismissable=True,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return NotificationBuilder

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Notification:
        return await create_test_notification_entry(fixture)


SELECT_ALL_STMT = "SELECT maasserver_notification.id, maasserver_notification.created, maasserver_notification.updated, maasserver_notification.ident, maasserver_notification.users, maasserver_notification.admins, maasserver_notification.message, maasserver_notification.context, maasserver_notification.user_id, maasserver_notification.category, maasserver_notification.dismissable"


class TestNotificationsRepository:
    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> NotificationsRepository:
        return NotificationsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def test_user(self, fixture: Fixture) -> User:
        return await create_test_user(
            fixture, username="user", is_superuser=False
        )

    @pytest.fixture
    async def test_admin(self, fixture: Fixture) -> User:
        return await create_test_user(
            fixture, username="admin", is_superuser=True
        )

    @pytest.fixture
    async def active_notification_for_user(
        self, fixture: Fixture
    ) -> Notification:
        return await create_test_notification_entry(
            fixture, ident="users_active", users=True, admins=False
        )

    @pytest.fixture
    async def active_notification_for_admin(
        self, fixture: Fixture
    ) -> Notification:
        return await create_test_notification_entry(
            fixture, ident="admins_active", users=False, admins=True
        )

    @pytest.fixture
    async def dismissed_notification_for_user(
        self,
        fixture: Fixture,
        test_user: User,
    ) -> Notification:
        notification = await create_test_notification_entry(
            fixture, ident="users_dismissed", users=True, admins=False
        )

        await create_test_notification_dismissal_entry(
            fixture,
            user_id=test_user.id,
            notification_id=notification.id,
        )
        return notification

    @pytest.fixture
    async def dismissed_notification_for_admin(
        self,
        fixture: Fixture,
        test_admin: User,
    ) -> Notification:
        notification = await create_test_notification_entry(
            fixture, ident="admins_dismissed", users=False, admins=True
        )
        await create_test_notification_dismissal_entry(
            fixture,
            user_id=test_admin.id,
            notification_id=notification.id,
        )
        return notification

    @pytest.mark.parametrize("is_admin", [True, False])
    def test_all_notification_for_user_stmt(
        self, repository: NotificationsRepository, is_admin: bool
    ) -> None:
        stmt = repository.all_notifications_for_user_stmt(
            user_id=1, is_admin=is_admin
        )

        if is_admin:
            condition = "maasserver_notification.admins = true"
        else:
            condition = "maasserver_notification.users = true"

        expected_stmt = (
            f"{SELECT_ALL_STMT} \n"
            "FROM maasserver_notification \n"
            f"WHERE maasserver_notification.user_id = 1 OR {condition}"
        )
        assert (
            str(stmt.compile(compile_kwargs={"literal_binds": True}))
            == expected_stmt
        )

    @pytest.mark.parametrize("is_admin", [True, False])
    def test_active_notification_for_user_stmt(
        self, repository: NotificationsRepository, is_admin: bool
    ) -> None:
        stmt = repository.active_notifications_for_user_stmt(
            user_id=1, is_admin=is_admin
        )
        if is_admin:
            condition = "maasserver_notification.admins = true"
        else:
            condition = "maasserver_notification.users = true"
        expected_stmt = (
            f"{SELECT_ALL_STMT} \n"
            "FROM maasserver_notification LEFT OUTER JOIN maasserver_notificationdismissal "
            "ON maasserver_notification.id = maasserver_notificationdismissal.notification_id "
            "AND maasserver_notificationdismissal.user_id = 1 \n"
            f"WHERE (maasserver_notification.user_id = 1 OR {condition}) AND maasserver_notificationdismissal.id IS NULL"
        )
        assert (
            str(stmt.compile(compile_kwargs={"literal_binds": True}))
            == expected_stmt
        )

    async def test_get_by_id_for_user(
        self,
        repository: NotificationsRepository,
        test_user: User,
        active_notification_for_user: Notification,
    ) -> None:
        notification = await repository.get_by_id_for_user(
            notification_id=active_notification_for_user.id,
            user_id=test_user.id,
            is_admin=test_user.is_superuser,
        )
        assert notification == active_notification_for_user

    async def test_get_by_id_for_user_not_found(
        self,
        repository: NotificationsRepository,
        test_user: User,
        active_notification_for_admin: Notification,
    ) -> None:
        notification = await repository.get_by_id_for_user(
            notification_id=active_notification_for_admin.id,
            user_id=test_user.id,
            is_admin=test_user.is_superuser,
        )
        assert notification is None

    async def test_list_active_for_user__user(
        self,
        repository: NotificationsRepository,
        test_user: User,
        active_notification_for_user: Notification,
        dismissed_notification_for_user: Notification,
        active_notification_for_admin: Notification,
        dismissed_notification_for_admin: Notification,
    ) -> None:
        notifications = await repository.list_active_for_user(
            page=1,
            size=10,
            user_id=test_user.id,
            is_admin=test_user.is_superuser,
        )
        assert len(notifications.items) == 1
        assert active_notification_for_user in notifications.items
        assert dismissed_notification_for_user not in notifications.items
        assert active_notification_for_admin not in notifications.items
        assert dismissed_notification_for_admin not in notifications.items

    async def test_list_active_for_user__admin(
        self,
        repository: NotificationsRepository,
        test_admin: User,
        active_notification_for_user: Notification,
        dismissed_notification_for_user: Notification,
        active_notification_for_admin: Notification,
        dismissed_notification_for_admin: Notification,
    ) -> None:
        notifications = await repository.list_active_for_user(
            page=1,
            size=10,
            user_id=test_admin.id,
            is_admin=test_admin.is_superuser,
        )
        assert len(notifications.items) == 1
        assert active_notification_for_admin in notifications.items
        assert dismissed_notification_for_admin not in notifications.items
        assert active_notification_for_user not in notifications.items
        assert dismissed_notification_for_user not in notifications.items

    async def test_list_all_for_user__user(
        self,
        repository: NotificationsRepository,
        test_user: User,
        active_notification_for_user: Notification,
        dismissed_notification_for_user: Notification,
        active_notification_for_admin: Notification,
        dismissed_notification_for_admin: Notification,
    ) -> None:
        notifications = await repository.list_all_for_user(
            page=1,
            size=10,
            user_id=test_user.id,
            is_admin=test_user.is_superuser,
        )
        assert len(notifications.items) == 2
        assert active_notification_for_user in notifications.items
        assert dismissed_notification_for_user in notifications.items
        assert active_notification_for_admin not in notifications.items
        assert dismissed_notification_for_admin not in notifications.items

    async def test_list_all_for_user__admin(
        self,
        repository: NotificationsRepository,
        test_admin: User,
        active_notification_for_user: Notification,
        dismissed_notification_for_user: Notification,
        active_notification_for_admin: Notification,
        dismissed_notification_for_admin: Notification,
    ) -> None:
        notifications = await repository.list_all_for_user(
            page=1,
            size=10,
            user_id=test_admin.id,
            is_admin=test_admin.is_superuser,
        )
        assert len(notifications.items) == 2
        assert active_notification_for_admin in notifications.items
        assert dismissed_notification_for_admin in notifications.items
        assert active_notification_for_user not in notifications.items
        assert dismissed_notification_for_user not in notifications.items

    async def test_delete_deletes_notification_dismissal(
        self,
        fixture: Fixture,
        repository: NotificationsRepository,
        dismissed_notification_for_user: Notification,
    ) -> None:
        await repository.delete_by_id(dismissed_notification_for_user.id)
        dismissed = await fixture.get(
            NotificationDismissalTable.name,
            eq(
                NotificationDismissalTable.c.notification_id,
                dismissed_notification_for_user.id,
            ),
        )
        assert dismissed == []

    async def test_create_notification_dismissal_entry(
        self,
        fixture: Fixture,
        repository: NotificationsRepository,
        test_user: User,
        active_notification_for_user: Notification,
    ) -> None:
        await repository.create_notification_dismissal(
            notification_id=active_notification_for_user.id,
            user_id=test_user.id,
        )
        [dismissed] = await fixture.get_typed(
            NotificationDismissalTable.name,
            NotificationDismissal,
            eq(
                NotificationDismissalTable.c.notification_id,
                active_notification_for_user.id,
            ),
        )
        assert dismissed is not None
        assert dismissed.notification_id == active_notification_for_user.id
        assert dismissed.user_id == test_user.id
