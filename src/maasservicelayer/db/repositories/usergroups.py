# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import desc, func, select, Table
from sqlalchemy.sql.functions import count

from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import UserGroupMembersView, UserGroupTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.usergroups import UserGroup, UserGroupStatistics


class UserGroupsClauseFactory(ClauseFactory):
    @classmethod
    def with_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=UserGroupTable.c.id.in_(ids))

    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=UserGroupTable.c.name == name)

    @classmethod
    def with_name_like(cls, name: str) -> Clause:
        return Clause(condition=UserGroupTable.c.name.ilike(f"%{name}%"))


class UserGroupsRepository(BaseRepository[UserGroup]):
    def get_repository_table(self) -> Table:
        return UserGroupTable

    def get_model_factory(self) -> Type[UserGroup]:
        return UserGroup

    async def list_groups_statistics(
        self,
        page: int,
        size: int,
        query: QuerySpec | None = None,
    ) -> ListResult[UserGroupStatistics]:
        total_stmt = select(count()).select_from(UserGroupTable)
        if query and query.where:
            where_query = QuerySpec(where=query.where)
            total_stmt = where_query.enrich_stmt(total_stmt)
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        groups_stmt = select(
            UserGroupTable.c.id,
        )
        if query and query.where:
            groups_stmt = QuerySpec(where=query.where).enrich_stmt(groups_stmt)
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
            items=[UserGroupStatistics(**row._asdict()) for row in result],
            total=total,
        )
