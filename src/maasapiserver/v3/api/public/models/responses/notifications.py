#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Self

from markupsafe import Markup
from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.notifications import Notification


class NotificationResponse(HalResponse[BaseHal]):
    kind: str = Field(default="Notification")
    id: int
    ident: str | None = None
    users: bool
    admins: bool
    message: str
    context: dict[str, Any]
    user_id: int | None = None
    category: str
    dismissable: bool

    @classmethod
    def from_model(
        cls, notification: Notification, self_base_hyperlink: str
    ) -> Self:
        markup = Markup(notification.message)
        markup = markup.format(**notification.context)
        return cls(
            id=notification.id,
            ident=notification.ident,
            users=notification.users,
            admins=notification.admins,
            message=str(markup),
            context=notification.context,
            user_id=notification.user_id,
            category=notification.category,
            dismissable=notification.dismissable,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{notification.id}"
                )
            ),
        )


class NotificationsListResponse(PaginatedResponse[NotificationResponse]):
    kind: str = Field(default="NotificationsList")
