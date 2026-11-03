#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.notifications import Notification


@dataclass(frozen=True)
class NotificationsForUserFilter(CustomFilter):
    model: ClassVar[type[Notification]] = Notification
    user_id: int
    is_admin: bool


@dataclass(frozen=True)
class NotificationsNotDismissedByUserFilter(CustomFilter):
    model: ClassVar[type[Notification]] = Notification
    user_id: int


class NotificationsFilters(FilterFactory):
    model = Notification

    @classmethod
    def with_user_id(cls, user_id: int) -> FieldFilter:
        return cls._equals("user_id", user_id)

    @classmethod
    def with_ident(cls, ident: str) -> FieldFilter:
        return cls._equals("ident", ident)

    @classmethod
    def for_user(
        cls, user_id: int, is_admin: bool
    ) -> NotificationsForUserFilter:
        return NotificationsForUserFilter(user_id, is_admin)

    @classmethod
    def not_dismissed_by_user(
        cls, user_id: int
    ) -> NotificationsNotDismissedByUserFilter:
        return NotificationsNotDismissedByUserFilter(user_id)
