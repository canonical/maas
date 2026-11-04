#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import or_, select

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import (
    NotificationDismissalTable,
    NotificationTable,
)
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.notifications import (
    NotificationsForUserFilter,
    NotificationsNotDismissedByUserFilter,
)
from maasservicelayer.models.notifications import Notification


class NotificationsDomainDataMapper(DefaultDomainDataMapper[Notification]):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case NotificationsForUserFilter(user_id, is_admin):
                role = (
                    NotificationTable.c.admins
                    if is_admin
                    else NotificationTable.c.users
                )
                return Clause(
                    condition=or_(
                        NotificationTable.c.user_id == user_id,
                        role.is_(True),
                    )
                )
            case NotificationsNotDismissedByUserFilter(user_id):
                dismissal = select(NotificationDismissalTable.c.id).where(
                    NotificationDismissalTable.c.notification_id
                    == NotificationTable.c.id,
                    NotificationDismissalTable.c.user_id == user_id,
                )
                return Clause(condition=~dismissal.exists())
        return super().custom_filter_clause(filter)
