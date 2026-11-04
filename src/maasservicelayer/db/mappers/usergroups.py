# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import UserGroupTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.usergroups import UserGroupNameLike
from maasservicelayer.models.usergroups import UserGroup


class UserGroupsDataMapper(DefaultDomainDataMapper[UserGroup]):
    def __init__(self):
        super().__init__(UserGroup, UserGroupTable)

    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case UserGroupNameLike(name):
                return Clause(
                    condition=UserGroupTable.c.name.ilike(f"%{name}%")
                )
            case _:
                return super().custom_filter_clause(filter)
