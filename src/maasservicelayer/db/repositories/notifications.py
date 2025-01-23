#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import NotificationTable
from maasservicelayer.models.notifications import Notification


class NotificationsClauseFactory(ClauseFactory):
    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(NotificationTable.c.user_id, user_id))


class NotificationsRepository(BaseRepository[Notification]):
    def get_repository_table(self) -> Table:
        return NotificationTable

    def get_model_factory(self) -> type[Notification]:
        return Notification
