#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import SSLKeyTable
from maasservicelayer.models.sslkeys import SSLKey


class SSLKeyClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(SSLKeyTable.c.id, id))

    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(SSLKeyTable.c.user_id, user_id))

    @classmethod
    def with_key(cls, key: str) -> Clause:
        return Clause(condition=eq(SSLKeyTable.c.key, key))


class SSLKeysRepository(BaseRepository[SSLKey]):
    def get_repository_table(self) -> Table:
        return SSLKeyTable

    def get_model_factory(self) -> Type[SSLKey]:
        return SSLKey

    async def update_one(self, query, builder):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def update_many(self, query, builder):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def update_by_id(self, id, builder):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def _update(self, query, builder):
        raise NotImplementedError("Update is not supported for SSL keys")
