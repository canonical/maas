# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from typing import Any

from maasservicelayer.models.notifications import (
    Notification,
    NotificationDismissal,
)
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_notification_entry(
    fixture: Fixture, **extra_details: Any
) -> Notification:
    now = utcnow()
    notification = {
        "created": now,
        "updated": now,
        "ident": "deprecation_MD5_users",
        "message": "Foo is deprecated, please update",
        "users": True,
        "admins": False,
        "context": {},
        "user_id": None,
        "category": "warning",
        "dismissable": True,
    }

    notification.update(extra_details)
    [created_notification] = await fixture.create(
        "maasserver_notification", [notification]
    )
    return Notification(**created_notification)


async def create_test_notification_dismissal_entry(
    fixture: Fixture,
    user_id: int,
    notification_id: int,
) -> NotificationDismissal:
    now = utcnow()
    notification_dismissal = {
        "created": now,
        "updated": now,
        "user_id": user_id,
        "notification_id": notification_id,
    }
    [created_notification_dismissal] = await fixture.create(
        "maasserver_notificationdismissal", [notification_dismissal]
    )
    return NotificationDismissal(**created_notification_dismissal)
