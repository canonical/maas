# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import ReadOnlyRepository
from maasservicelayer.db.tables import UserGroupMembersView
from maasservicelayer.models.usergroup_members import UserGroupMember


class UserGroupMembersClauseFactory(ClauseFactory):
    @classmethod
    def with_group_id(cls, group_id: int) -> Clause:
        return Clause(condition=eq(UserGroupMembersView.c.group_id, group_id))

    @classmethod
    def with_username(cls, username: str) -> Clause:
        return Clause(condition=eq(UserGroupMembersView.c.username, username))

    @classmethod
    def with_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(UserGroupMembersView.c.id, user_id))


class UserGroupMembersRepository(ReadOnlyRepository[UserGroupMember]):
    def get_repository_table(self) -> Table:
        return UserGroupMembersView

    def get_model_factory(self) -> Type[UserGroupMember]:
        return UserGroupMember
