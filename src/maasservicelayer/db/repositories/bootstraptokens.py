# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootstrapTokenTable
from maasservicelayer.models.bootstraptokens import BootstrapToken


class BootstrapTokensRepository(BaseRepository[BootstrapToken]):
    def get_repository_table(self) -> Table:
        return BootstrapTokenTable

    def get_model_factory(self) -> type[BootstrapToken]:
        return BootstrapToken
