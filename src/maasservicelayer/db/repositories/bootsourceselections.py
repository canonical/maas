# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import BootSourceSelectionTable
from maasservicelayer.models.bootsourceselections import BootSourceSelection


class BootSourceSelectionClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(BootSourceSelectionTable.c.id, id))

    @classmethod
    def with_boot_source_id(cls, boot_source_id: int) -> Clause:
        return Clause(
            condition=eq(
                BootSourceSelectionTable.c.boot_source_id, boot_source_id
            )
        )

    @classmethod
    def with_os(cls, os: str) -> Clause:
        return Clause(condition=eq(BootSourceSelectionTable.c.os, os))

    @classmethod
    def with_release(cls, release: str) -> Clause:
        return Clause(
            condition=eq(BootSourceSelectionTable.c.release, release)
        )

    @classmethod
    def with_all_arches(cls) -> Clause:
        return Clause(condition=eq(BootSourceSelectionTable.c.arches, ["*"]))

    @classmethod
    def with_all_subarches(cls) -> Clause:
        return Clause(
            condition=eq(BootSourceSelectionTable.c.subarches, ["*"])
        )

    @classmethod
    def with_all_labels(cls) -> Clause:
        return Clause(condition=eq(BootSourceSelectionTable.c.labels, ["*"]))


class BootSourceSelectionsRepository(BaseRepository[BootSourceSelection]):
    def get_repository_table(self) -> Table:
        return BootSourceSelectionTable

    def get_model_factory(self) -> type[BootSourceSelection]:
        return BootSourceSelection
