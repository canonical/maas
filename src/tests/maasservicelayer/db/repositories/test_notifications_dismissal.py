# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.notification_dismissal import (
    NotificationDismissalsClauseFactory,
    NotificationDismissalsRepository,
)
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.notification_dismissal import (
    NotificationDismissal,
    NotificationDismissalBuilder,
)
from tests.fixtures.factories.notifications import (
    create_test_notification_dismissal_entry,
    create_test_notification_entry,
)
from tests.fixtures.factories.user import create_test_user
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestNotificationDismissalsClauseFactory:
    def test_with_user_id(self) -> None:
        clause = NotificationDismissalsClauseFactory.with_user_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_notificationdismissal.user_id = 1"
        )


class TestNotificationDismissalRepository(
    RepositoryCommonTests[NotificationDismissal]
):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> NotificationDismissalsRepository:
        return NotificationDismissalsRepository(
            Context(connection=db_connection)
        )

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[NotificationDismissal]:
        notification_dismissals = []
        user = await create_test_user(fixture)
        for i in range(num_objects):
            notification = await create_test_notification_entry(
                fixture, ident=str(i)
            )
            notification_dismissals.append(
                await create_test_notification_dismissal_entry(
                    fixture, user.id, notification.id
                )
            )
        return notification_dismissals

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs) -> ResourceBuilder:
        return NotificationDismissalBuilder(user_id=1, notification_id=1)

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return NotificationDismissalBuilder

    @pytest.fixture
    async def created_instance(
        self, fixture: Fixture
    ) -> NotificationDismissal:
        user = await create_test_user(fixture)
        notification = await create_test_notification_entry(fixture)
        return await create_test_notification_dismissal_entry(
            fixture, user.id, notification.id
        )

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    async def test_update_one(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one(
                repository_instance, instance_builder
            )

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_one_multiple_results(
        self,
        repository_instance,
        instance_builder_model,
        _setup_test_list,
        num_objects,
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_multiple_results(
                repository_instance,
                instance_builder_model,
                _setup_test_list,
                num_objects,
            )

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_many(
        self,
        repository_instance,
        instance_builder_model,
        _setup_test_list,
        num_objects,
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_many(
                repository_instance,
                instance_builder_model,
                _setup_test_list,
                num_objects,
            )

    async def test_update_by_id(self, repository_instance, instance_builder):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id(
                repository_instance, instance_builder
            )
