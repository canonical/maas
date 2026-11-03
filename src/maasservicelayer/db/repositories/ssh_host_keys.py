# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import TrustedSshHostKeyTable
from maasservicelayer.models.ssh_host_keys import TrustedSshHostKey


class TrustedSshHostKeyRepository(BaseRepository[TrustedSshHostKey]):
    def get_repository_table(self) -> Table:
        return TrustedSshHostKeyTable

    def get_model_factory(self) -> Type[TrustedSshHostKey]:
        return TrustedSshHostKey
