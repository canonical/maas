# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootSourceSelectionLegacyTable
from maasservicelayer.models.legacybootsourceselections import (
    LegacyBootSourceSelection,
)


# TODO: MAASENG-5738 remove this
class LegacyBootSourceSelectionRepository(
    BaseRepository[LegacyBootSourceSelection]
):
    def get_repository_table(self) -> Table:
        return BootSourceSelectionLegacyTable

    def get_model_factory(self) -> type[LegacyBootSourceSelection]:
        return LegacyBootSourceSelection
