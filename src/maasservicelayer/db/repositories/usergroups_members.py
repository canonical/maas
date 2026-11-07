# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import ReadOnlyRepository
from maasservicelayer.db.tables import UserGroupMembersView
from maasservicelayer.models.usergroup_members import UserGroupMember


class UserGroupMembersRepository(ReadOnlyRepository[UserGroupMember]):
    def get_repository_table(self) -> Table:
        return UserGroupMembersView

    def get_model_factory(self) -> Type[UserGroupMember]:
        return UserGroupMember
