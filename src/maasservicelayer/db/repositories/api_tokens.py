#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table
from sqlalchemy.sql.operators import eq, is_

from maasservicelayer.db.filters import Clause, ClauseFactory, OrderByClause
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ApiTokenTable
from maasservicelayer.models.tokens import ApiToken


class ApiTokenClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(ApiTokenTable.c.id, id))

    @classmethod
    def with_public_id(cls, public_id: str) -> Clause:
        return Clause(condition=eq(ApiTokenTable.c.public_id, public_id))

    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(ApiTokenTable.c.user_id, user_id))

    @classmethod
    def not_revoked(cls) -> Clause:
        return Clause(condition=is_(ApiTokenTable.c.revoked_at, None))


class ApiTokenOrderByClauses:
    @staticmethod
    def last_used_at_desc() -> list[OrderByClause]:
        return [
            OrderByClause(ApiTokenTable.c.last_used_at.desc().nulls_last()),
            OrderByClause(ApiTokenTable.c.id.desc()),
        ]


class ApiTokenRepository(BaseRepository[ApiToken]):
    def get_repository_table(self) -> Table:
        return ApiTokenTable

    def get_model_factory(self) -> type[ApiToken]:
        return ApiToken
