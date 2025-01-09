# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import SshKeyTable
from maasservicelayer.models.sshkeys import SshKey


class SshKeyClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(SshKeyTable.c.id, id))

    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(SshKeyTable.c.user_id, user_id))


class SshKeysRepository(BaseRepository[SshKey]):
    def get_repository_table(self) -> Table:
        return SshKeyTable

    def get_model_factory(self) -> Type[SshKey]:
        return SshKey

    async def update_one(self, query, resource):
        raise NotImplementedError("Update is not supported for ssh keys")

    async def update_many(self, query, resource):
        raise NotImplementedError("Update is not supported for ssh keys")

    async def update_by_id(self, id, resource):
        raise NotImplementedError("Update is not supported for ssh keys")

    async def _update(self, query, resource):
        raise NotImplementedError("Update is not supported for ssh keys")
