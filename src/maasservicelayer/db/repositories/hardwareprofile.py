# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import HardwareProfileTable
from maasservicelayer.models.hardwareprofile import HardwareProfile


class HardwareProfileRepository(BaseRepository[HardwareProfile]):
    def get_repository_table(self) -> Table:
        return HardwareProfileTable

    def get_model_factory(self) -> type[HardwareProfile]:
        return HardwareProfile
