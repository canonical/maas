# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.notifications import (
    NotificationResponse,
)
from maascommon.enums.notifications import NotificationCategoryEnum
from maasservicelayer.models.notifications import Notification


class TestNotificationResponse:
    def test_from_model(self) -> None:
        notification = Notification(
            id=1,
            ident="MAAS update",
            message="MAAS has been upgraded to {version}.",
            users=True,
            admins=False,
            context={"version": "3.6.0"},
            user_id=None,
            category=NotificationCategoryEnum.INFO,
            dismissable=True,
        )

        notification_response = NotificationResponse.from_model(
            notification, self_base_hyperlink="http://test"
        )
        assert notification_response.kind == "Notification"
        assert notification_response.id == notification.id
        assert notification_response.ident == notification.ident
        assert (
            notification_response.message == "MAAS has been upgraded to 3.6.0."
        )
        assert notification_response.context == notification.context
        assert notification_response.user_id == notification.user_id
        assert notification_response.category == NotificationCategoryEnum.INFO
        assert notification_response.dismissable == notification.dismissable
