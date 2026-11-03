# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import SshKeyTable
from maasservicelayer.models.sshkeys import SshKey


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
