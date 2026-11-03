# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import desc, func, select, Table
from sqlalchemy.sql.functions import count

from maasservicelayer.context import Context
from maasservicelayer.db.filters import SQLQuerySpec
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.mappers.usergroups import UserGroupsDataMapper
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import UserGroupMembersView, UserGroupTable
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.usergroups import UserGroup, UserGroupStatistics


class UserGroupsRepository(BaseRepository[UserGroup]):
    def __init__(self, context: Context):
        super().__init__(context)
        self.statistics_mapper = DefaultDomainDataMapper[UserGroupStatistics](
            UserGroupStatistics, UserGroupTable
        )

    def get_repository_table(self) -> Table:
        return UserGroupTable

    def get_model_factory(self) -> Type[UserGroup]:
        return UserGroup

    def get_mapper(self) -> UserGroupsDataMapper:
        return UserGroupsDataMapper()

    async def list_groups_statistics(
        self,
        page: int,
        size: int,
        query: QuerySpec | None = None,
    ) -> ListResult[UserGroupStatistics]:
        sql_query = (
            SQLQuerySpec(where=self._translate(query).where)
            if query is not None
            else None
        )
        total_stmt = select(count()).select_from(UserGroupTable)
        if sql_query is not None:
            total_stmt = sql_query.enrich_stmt(total_stmt)
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        groups_stmt = select(
            UserGroupTable.c.id,
        )
        if sql_query is not None:
            groups_stmt = sql_query.enrich_stmt(groups_stmt)
        groups_subq = groups_stmt.subquery()

        stmt = (
            select(
                groups_subq.c.id,
                func.count(UserGroupMembersView.c.id).label("user_count"),
            )
            .select_from(
                groups_subq.outerjoin(
                    UserGroupMembersView,
                    UserGroupMembersView.c.group_id == groups_subq.c.id,
                )
            )
            .group_by(groups_subq.c.id)
            .order_by(desc(groups_subq.c.id))
            .offset((page - 1) * size)
            .limit(size)
        )

        result = (await self.execute_stmt(stmt)).all()
        return ListResult[UserGroupStatistics](
            items=[
                self.statistics_mapper.to_domain(row._mapping)
                for row in result
            ],
            total=total,
        )
