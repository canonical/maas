# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootSourceTable
from maasservicelayer.models.bootsources import BootSource


class BootSourcesRepository(BaseRepository[BootSource]):
    def get_repository_table(self) -> Table:
        return BootSourceTable

    def get_model_factory(self) -> type[BootSource]:
        return BootSource
