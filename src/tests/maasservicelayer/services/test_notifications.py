#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.notifications import (
    NotificationsRepository,
)
from maasservicelayer.models.notifications import Notification
from maasservicelayer.services.notifications import NotificationsService
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestNotificationsService(ServiceCommonTests):
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
            category="warning",
            dismissable=True,
        )
