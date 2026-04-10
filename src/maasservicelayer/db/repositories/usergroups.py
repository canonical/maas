# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Type

from sqlalchemy import desc, func, select, Table
from sqlalchemy.sql.functions import count

from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import UserGroupMembersView, UserGroupTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.usergroups import (
    UserGroup,
    UserGroupWithUserCount,
)


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

    async def list_with_user_count(
        self,
        page: int,
        size: int,
        query: Optional[QuerySpec] = None,
    ) -> ListResult[UserGroupWithUserCount]:
        total_stmt = select(count()).select_from(UserGroupTable)
        if query and query.where:
            where_query = QuerySpec(where=query.where)
            total_stmt = where_query.enrich_stmt(total_stmt)
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = (
            select(
                UserGroupTable.c.id,
                UserGroupTable.c.name,
                UserGroupTable.c.description,
                UserGroupTable.c.created,
                UserGroupTable.c.updated,
                func.count(UserGroupMembersView.c.id).label("user_count"),
            )
            .select_from(
                UserGroupTable.outerjoin(
                    UserGroupMembersView,
                    UserGroupMembersView.c.group_id == UserGroupTable.c.id,
                )
            )
            .group_by(UserGroupTable.c.id)
            .order_by(desc(UserGroupTable.c.id))
            .offset((page - 1) * size)
            .limit(size)
        )
        if query:
            stmt = query.enrich_stmt(stmt)

        result = (await self.execute_stmt(stmt)).all()
        return ListResult[UserGroupWithUserCount](
            items=[UserGroupWithUserCount(**row._asdict()) for row in result],
            total=total,
        )
