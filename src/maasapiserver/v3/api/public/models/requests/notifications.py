# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from pydantic import BaseModel, Field, root_validator

from maascommon.enums.notifications import NotificationCategoryEnum
from maasservicelayer.builders.notifications import NotificationBuilder


class NotificationRequest(BaseModel):
    message: str = Field(
        description="The message for this notification. May contain basic HTML,"
        "such as formatting. This string will be sanitised before display so"
        "that it doesn't break MAAS HTML."
    )
    category: NotificationCategoryEnum = Field(
        description="Choose from: ``error``,"
        "``warning``, ``success``, or ``info``. Defaults to ``info``.",
        default=NotificationCategoryEnum.INFO,
    )
    ident: str | None = Field(
        description="Unique identifier for this notification."
    )
    user_id: int | None = Field(
        description="User ID this notification is intended for."
        "By default it will not be targeted to any individual user."
    )
    for_users: bool = Field(
        description="True to notify all users,"
        "defaults to false, i.e. not targeted to all users.",
        default=False,
    )
    for_admins: bool = Field(
        description="True to notify all admins,"
        "defaults to false, i.e. not targeted to all admins.",
        default=False,
    )
    context: dict = Field(
        description="Optional JSON context. The root object *must* be an object"
        "(i.e. a mapping). The values herein can be referenced by ``message``"
        "with Python's 'format' (not %) codes.",
        default={},
    )
    dismissable: bool = Field(
        description="Wheter this notification can be dismissed or not. Defaults to True.",
        default=True,
    )

    @root_validator
    def validate_recipient(cls, values: dict[str, Any]):
        if (
            values["user_id"] is None
            and values["for_users"] is False
            and values["for_admins"] is False
        ):
            raise ValueError(
                "Either 'user_id', 'for_users' or 'for_admin' must be specified."
            )
        return values

    def to_builder(self) -> NotificationBuilder:
        return NotificationBuilder(
            message=self.message,
            category=self.category,
            ident=self.ident,
            user_id=self.user_id,
            users=self.for_users,
            admins=self.for_admins,
            context=self.context,
            dismissable=self.dismissable,
        )
