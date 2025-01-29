#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.notifications import (
    NotificationsRepository,
)
from maasservicelayer.models.notifications import (
    Notification,
    NotificationBuilder,
)
from maasservicelayer.services.base import BaseService, ServiceCache


class NotificationsService(
    BaseService[Notification, NotificationsRepository, NotificationBuilder]
):
    def __init__(
        self,
        context: Context,
        repository: NotificationsRepository,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
