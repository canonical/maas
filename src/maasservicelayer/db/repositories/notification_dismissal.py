#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import NotificationDismissalTable
from maasservicelayer.models.notification_dismissal import (
    NotificationDismissal,
)


class NotificationDismissalsClauseFactory(ClauseFactory):
    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(
            condition=eq(NotificationDismissalTable.c.user_id, user_id)
        )


class NotificationDismissalsRepository(BaseRepository[NotificationDismissal]):
    def get_repository_table(self) -> Table:
        return NotificationDismissalTable

    def get_model_factory(self) -> type[NotificationDismissal]:
        return NotificationDismissal

    async def update_one(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for notification dismissals."
        )

    async def update_many(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for notification dismissals."
        )

    async def update_by_id(self, id, builder):
        raise NotImplementedError(
            "Update is not supported for notification dismissals."
        )

    async def _update(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for notification dismissals."
        )
