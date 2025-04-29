# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import MDNSTable
from maasservicelayer.models.mdns import MDNS


class MDNSRepository(BaseRepository[MDNS]):
    def get_repository_table(self) -> Table:
        return MDNSTable

    def get_model_factory(self) -> type[MDNS]:
        return MDNS
