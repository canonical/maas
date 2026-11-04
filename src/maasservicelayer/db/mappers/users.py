# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import join, or_

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import UserProfileTable, UserTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.users import UsernameOrEmailLike, UserProviderId
from maasservicelayer.models.users import User


class UsersDataMapper(DefaultDomainDataMapper):
    def __init__(self):
        super().__init__(User, UserTable)

    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case UsernameOrEmailLike(value):
                return Clause(
                    condition=or_(
                        UserTable.c.username.ilike(f"%{value}%"),
                        UserTable.c.email.ilike(f"%{value}%"),
                    )
                )
            case UserProviderId(provider_id):
                return Clause(
                    condition=UserProfileTable.c.provider_id == provider_id,
                    joins=[
                        join(
                            UserTable,
                            UserProfileTable,
                            UserTable.c.id == UserProfileTable.c.user_id,
                        )
                    ],
                )
            case _:
                return super().custom_filter_clause(filter)
