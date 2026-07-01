# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import TrustedSshHostKeyTable
from maasservicelayer.models.ssh_host_keys import TrustedSshHostKey


class TrustedSshHostKeyClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(TrustedSshHostKeyTable.c.id, id))

    @classmethod
    def with_host(cls, host: str) -> Clause:
        return Clause(condition=eq(TrustedSshHostKeyTable.c.host, host))

    @classmethod
    def with_key_type(cls, key_type: str) -> Clause:
        return Clause(
            condition=eq(TrustedSshHostKeyTable.c.key_type, key_type)
        )

    @classmethod
    def with_public_key(cls, public_key: str) -> Clause:
        return Clause(
            condition=eq(TrustedSshHostKeyTable.c.public_key, public_key)
        )


class TrustedSshHostKeyRepository(BaseRepository[TrustedSshHostKey]):
    def get_repository_table(self) -> Table:
        return TrustedSshHostKeyTable

    def get_model_factory(self) -> Type[TrustedSshHostKey]:
        return TrustedSshHostKey
