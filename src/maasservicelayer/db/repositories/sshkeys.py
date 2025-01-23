# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import Table

from maascommon.enums.sshkeys import SshKeysProtocolType
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

    @classmethod
    def with_key(cls, key: str) -> Clause:
        return Clause(condition=eq(SshKeyTable.c.key, key))

    @classmethod
    def with_protocol(cls, protocol: SshKeysProtocolType | None) -> Clause:
        return Clause(condition=eq(SshKeyTable.c.protocol, protocol))

    @classmethod
    def with_auth_id(cls, auth_id: str | None) -> Clause:
        return Clause(condition=eq(SshKeyTable.c.auth_id, auth_id))


class SshKeysRepository(BaseRepository[SshKey]):
    def get_repository_table(self) -> Table:
        return SshKeyTable

    def get_model_factory(self) -> Type[SshKey]:
        return SshKey

    async def update_one(self, query, builder):
        raise NotImplementedError("Update is not supported for ssh keys")

    async def update_many(self, query, builder):
        raise NotImplementedError("Update is not supported for ssh keys")

    async def update_by_id(self, id, builder):
        raise NotImplementedError("Update is not supported for ssh keys")

    async def _update(self, query, builder):
        raise NotImplementedError("Update is not supported for ssh keys")
