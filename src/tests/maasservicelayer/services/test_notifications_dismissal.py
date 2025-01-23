#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.notification_dismissal import (
    NotificationDismissalsRepository,
)
from maasservicelayer.models.notification_dismissal import (
    NotificationDismissal,
)
from maasservicelayer.services.notification_dismissal import (
    NotificationDismissalService,
)
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestNotificationDismissalService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> NotificationDismissalService:
        return NotificationDismissalService(
            context=Context(),
            repository=Mock(NotificationDismissalsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> NotificationDismissal:
        now = utcnow()
        return NotificationDismissal(
            id=1, created=now, updated=now, user_id=1, notification_id=1
        )

    async def test_update_many(self, service_instance, test_instance):
        with pytest.raises(NotImplementedError):
            return await super().test_update_many(
                service_instance, test_instance
            )

    async def test_update_one(self, service_instance, test_instance):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one(
                service_instance, test_instance
            )

    async def test_update_one_not_found(self, service_instance):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_not_found(service_instance)

    async def test_update_one_etag_match(
        self, service_instance, test_instance
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_etag_match(
                service_instance, test_instance
            )

    async def test_update_one_etag_not_matching(
        self, service_instance, test_instance
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_etag_not_matching(
                service_instance, test_instance
            )

    async def test_update_by_id(self, service_instance, test_instance):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id(
                service_instance, test_instance
            )

    async def test_update_by_id_not_found(self, service_instance):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_not_found(service_instance)

    async def test_update_by_id_etag_match(
        self, service_instance, test_instance
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_etag_match(
                service_instance, test_instance
            )

    async def test_update_by_id_etag_not_matching(
        self, service_instance, test_instance
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_etag_not_matching(
                service_instance, test_instance
            )
