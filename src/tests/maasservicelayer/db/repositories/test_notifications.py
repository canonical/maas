# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.notifications import NotificationBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.notifications import (
    NotificationsClauseFactory,
    NotificationsRepository,
)
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.notifications import Notification
from tests.fixtures.factories.notifications import (
    create_test_notification_entry,
)
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


class TestNotificationRepository(RepositoryCommonTests[Notification]):
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
            category="warning",
            dismissable=True,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return NotificationBuilder

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Notification:
        return await create_test_notification_entry(fixture)
