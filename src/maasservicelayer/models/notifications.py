# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Optional

from maascommon.enums.notifications import NotificationCategoryEnum
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Notification(MaasTimestampedBaseModel):
    ident: str | None
    users: bool
    admins: bool
    message: str
    context: dict[str, Any]
    user_id: Optional[int]
    category: NotificationCategoryEnum
    dismissable: bool


@generate_builder()
class NotificationDismissal(MaasTimestampedBaseModel):
    user_id: int
    notification_id: int
