# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Iterable
from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootSourceSelectionLegacyTable
from maasservicelayer.models.legacybootsourceselections import (
    LegacyBootSourceSelection,
)


class LegacyBootSourceSelectionClauseFactory(ClauseFactory):
    @classmethod
    def with_ids(cls, ids: Iterable[int]):
        return Clause(condition=BootSourceSelectionLegacyTable.c.id.in_(ids))

    @classmethod
    def with_boot_source_id(cls, boot_source_id: int):
        return Clause(
            condition=eq(
                BootSourceSelectionLegacyTable.c.boot_source_id,
                boot_source_id,
            )
        )

    @classmethod
    def with_os(cls, os: str):
        return Clause(
            condition=eq(
                BootSourceSelectionLegacyTable.c.os,
                os,
            )
        )

    @classmethod
    def with_release(cls, release: str):
        return Clause(
            condition=eq(
                BootSourceSelectionLegacyTable.c.release,
                release,
            )
        )


# TODO: MAASENG-5738 remove this
class LegacyBootSourceSelectionRepository(
    BaseRepository[LegacyBootSourceSelection]
):
    def get_repository_table(self) -> Table:
        return BootSourceSelectionLegacyTable

    def get_model_factory(self) -> type[LegacyBootSourceSelection]:
        return LegacyBootSourceSelection
