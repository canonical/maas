#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Self, Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
)
from maasservicelayer.db.tables import SSLKeyTable
from maasservicelayer.models.sslkeys import SSLKey


class SSLKeyClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(SSLKeyTable.c.id, id))

    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(SSLKeyTable.c.user_id, user_id))


class SSLKeyResourceBuilder(ResourceBuilder):
    def with_key(self, key: str) -> Self:
        self._request.set_value(SSLKeyTable.c.key.name, key)
        return self

    def with_user_id(self, user_id: int) -> Self:
        self._request.set_value(SSLKeyTable.c.user_id.name, user_id)
        return self


class SSLKeysRepository(BaseRepository[SSLKey]):

    def get_repository_table(self) -> Table:
        return SSLKeyTable

    def get_model_factory(self) -> Type[SSLKey]:
        return SSLKey

    async def update_one(self, query, resource):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def update_many(self, query, resource):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def update_by_id(self, id, resource):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def _update(self, query, resource):
        raise NotImplementedError("Update is not supported for SSL keys")
