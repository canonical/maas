#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.notification_dismissal import (
    NotificationDismissalBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.notification_dismissal import (
    NotificationDismissalsRepository,
)
from maasservicelayer.models.notification_dismissal import (
    NotificationDismissal,
)
from maasservicelayer.services.base import BaseService, ServiceCache


class NotificationDismissalService(
    BaseService[
        NotificationDismissal,
        NotificationDismissalsRepository,
        NotificationDismissalBuilder,
    ]
):
    def __init__(
        self,
        context: Context,
        repository: NotificationDismissalsRepository,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)

    async def update_by_id(self, id, builder, etag_if_match=None):
        raise NotImplementedError(
            "Update is not supported for notification dismissal"
        )

    async def update_many(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for notification dismissal"
        )

    async def update_one(self, query, builder, etag_if_match=None):
        raise NotImplementedError(
            "Update is not supported for notification dismissal"
        )

    async def _update_resource(
        self, existing_resource, builder, etag_if_match=None
    ):
        raise NotImplementedError(
            "Update is not supported for notification dismissal"
        )
