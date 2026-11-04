#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import List, override

from sqlalchemy import delete, desc, insert, select, Table
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import Select
from sqlalchemy.sql.functions import count

from maasservicelayer.builders.notifications import (
    NotificationDismissalBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.mappers.notifications import (
    NotificationsDomainDataMapper,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    NotificationDismissalTable,
    NotificationTable,
)
from maasservicelayer.filters.notifications import NotificationsFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.notifications import (
    Notification,
    NotificationDismissal,
)
from maasservicelayer.utils.date import utcnow


class NotificationsRepository(BaseRepository[Notification]):
    def __init__(self, context: Context):
        super().__init__(context)
        self.notificationdismissal_mapper = DefaultDomainDataMapper(
            NotificationDismissal, NotificationDismissalTable
        )

    def get_repository_table(self) -> Table:
        return NotificationTable

    def get_model_factory(self) -> type[Notification]:
        return Notification

    def get_mapper(self) -> NotificationsDomainDataMapper:
        return NotificationsDomainDataMapper(Notification, NotificationTable)

    def all_notifications_for_user_stmt(
        self, user_id: int, is_admin: bool
    ) -> Select:
        """Statement for all the notifications for the user."""
        return self._translate(
            QuerySpec(where=NotificationsFilters.for_user(user_id, is_admin))
        ).enrich_stmt(self.select_all_statement())

    def active_notifications_for_user_stmt(
        self, user_id: int, is_admin: bool
    ) -> Select:
        """Statement for all the non-dismissed notifications for the user."""
        return self._translate(
            QuerySpec(
                where=NotificationsFilters.and_filters(
                    [
                        NotificationsFilters.for_user(user_id, is_admin),
                        NotificationsFilters.not_dismissed_by_user(user_id),
                    ]
                )
            )
        ).enrich_stmt(self.select_all_statement())

    async def _list_with_stmt(
        self, page: int, size: int, stmt: Select
    ) -> ListResult[Notification]:
        total_stmt = select(count()).select_from(stmt.subquery())
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = (
            stmt.order_by(desc(self.get_repository_table().c.id))
            .offset((page - 1) * size)
            .limit(size)
        )

        result = (await self.execute_stmt(stmt)).all()
        return ListResult[Notification](
            items=[self.mapper.to_domain(row._mapping) for row in result],
            total=total,
        )

    async def list_all_for_user(
        self, page: int, size: int, user_id: int, is_admin: bool
    ) -> ListResult[Notification]:
        return await self._list_with_stmt(
            page=page,
            size=size,
            stmt=self.all_notifications_for_user_stmt(user_id, is_admin),
        )

    async def list_active_for_user(
        self, page: int, size: int, user_id: int, is_admin: bool
    ) -> ListResult[Notification]:
        return await self._list_with_stmt(
            page=page,
            size=size,
            stmt=self.active_notifications_for_user_stmt(user_id, is_admin),
        )

    async def get_by_id_for_user(
        self, notification_id: int, user_id: int, is_admin: bool
    ) -> Notification | None:
        stmt = self.all_notifications_for_user_stmt(user_id, is_admin).where(
            eq(NotificationTable.c.id, notification_id)
        )
        result = (await self.execute_stmt(stmt)).one_or_none()
        if result:
            return self.mapper.to_domain(result._mapping)
        else:
            return None

    async def create_notification_dismissal(
        self, notification_id: int, user_id: int
    ) -> None:
        now = utcnow()
        dismissal_builder = NotificationDismissalBuilder(
            user_id=user_id,
            notification_id=notification_id,
            created=now,
            updated=now,
        )

        resource = self.notificationdismissal_mapper.build_resource(
            dismissal_builder
        )

        stmt = insert(NotificationDismissalTable).values(
            **resource.get_values()
        )
        try:
            await self.execute_stmt(stmt)
        except IntegrityError:
            # Do nothing if the notification has been already dismissed
            pass

    async def delete_all_dismissal_for_notification(
        self,
        notification_id: int,
    ) -> None:
        stmt = delete(NotificationDismissalTable).where(
            eq(NotificationDismissalTable.c.notification_id, notification_id)
        )
        await self.execute_stmt(stmt)

    @override
    async def _delete(self, query: QuerySpec) -> List[Notification]:
        stmt = delete(NotificationTable).returning(self.get_repository_table())
        stmt = self._translate(query).enrich_stmt(stmt)
        results = (await self.execute_stmt(stmt)).all()
        deleted = [self.mapper.to_domain(row._mapping) for row in results]
        cascade_stmt = delete(NotificationDismissalTable).where(
            NotificationDismissalTable.c.notification_id.in_(
                [n.id for n in deleted]
            )
        )
        await self.execute_stmt(cascade_stmt)
        return deleted
