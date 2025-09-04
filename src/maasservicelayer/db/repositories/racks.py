# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import RackTable
from maasservicelayer.models.racks import Rack


class RacksRepository(BaseRepository[Rack]):
    def get_repository_table(self) -> Table:
        return RackTable

    def get_model_factory(self) -> type[Rack]:
        return Rack
