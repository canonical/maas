# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import UserGroupTable
from maasservicelayer.models.usergroups import UserGroup


class UserGroupsClauseFactory(ClauseFactory):
    @classmethod
    def with_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=UserGroupTable.c.id.in_(ids))

    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=UserGroupTable.c.name == name)


class UserGroupsRepository(BaseRepository[UserGroup]):
    def get_repository_table(self) -> Table:
        return UserGroupTable

    def get_model_factory(self) -> Type[UserGroup]:
        return UserGroup
