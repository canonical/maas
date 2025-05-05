# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from sqlalchemy import func, select, Table
from sqlalchemy.sql.operators import eq

from maascommon.enums.token import TokenType
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ConsumerTable, TokenTable, UserTable
from maasservicelayer.models.tokens import Token


class TokenClauseFactory(ClauseFactory):
    @classmethod
    def with_consumer_id(cls, consumer_id: int) -> Clause:
        return Clause(condition=eq(TokenTable.c.consumer_id, consumer_id))

    @classmethod
    def with_consumer_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=TokenTable.c.consumer_id.in_(ids))

    @classmethod
    def with_secret(cls, secret: str) -> Clause:
        return Clause(condition=eq(TokenTable.c.secret, secret))

    @classmethod
    def with_key(cls, key: str) -> Clause:
        return Clause(condition=eq(TokenTable.c.key, key))


class TokensRepository(BaseRepository[Token]):
    """
    Piston3 Token repository. See
    https://github.com/userzimmermann/django-piston3/blob/fe1ea644bcb07332670aeceddbf0ded29bdf785a/piston/models.py#L55 for
    reference.

    Remove this service once all the django and its OAuth method is removed from the codebase in favor of the new JWT approach.
    """

    def get_repository_table(self) -> Table:
        return TokenTable

    def get_model_factory(self) -> type[Token]:
        return Token

    async def get_user_apikeys(self, username: str) -> List[str]:
        stmt = (
            select(
                func.concat(
                    ConsumerTable.c.key,
                    ":",
                    TokenTable.c.key,
                    ":",
                    TokenTable.c.secret,
                )
            )
            .select_from(TokenTable)
            .join(UserTable, eq(TokenTable.c.user_id, UserTable.c.id))
            .join(
                ConsumerTable, eq(TokenTable.c.consumer_id, ConsumerTable.c.id)
            )
            .where(
                eq(UserTable.c.username, username),
                eq(TokenTable.c.token_type, TokenType.ACCESS),
                eq(TokenTable.c.is_approved, True),
            )
            .order_by(TokenTable.c.id)
        )

        result = (await self.execute_stmt(stmt)).all()
        return [str(row[0]) for row in result]
