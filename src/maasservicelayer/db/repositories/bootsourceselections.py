# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import List

from sqlalchemy import func, select, Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    BootSourceSelectionTable,
    BootSourceTable,
)
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
    def with_arch(cls, arch: str) -> Clause:
        return Clause(condition=eq(BootSourceSelectionTable.c.arch, arch))


class BootSourceSelectionsRepository(BaseRepository[BootSourceSelection]):
    def get_repository_table(self) -> Table:
        return BootSourceSelectionTable

    def get_model_factory(self) -> type[BootSourceSelection]:
        return BootSourceSelection

    async def get_all_highest_priority(self) -> List[BootSourceSelection]:
        subquery = (
            select(
                BootSourceSelectionTable,
                func.row_number()
                .over(
                    partition_by=[
                        BootSourceSelectionTable.c.os,
                        BootSourceSelectionTable.c.arch,
                        BootSourceSelectionTable.c.release,
                    ],
                    order_by=BootSourceTable.c.priority.desc(),
                )
                .label("rank"),
            )
            .select_from(BootSourceSelectionTable)
            .join(
                BootSourceTable,
                eq(
                    BootSourceSelectionTable.c.boot_source_id,
                    BootSourceTable.c.id,
                ),
            )
            .subquery()
        )
        stmt = (
            select(
                # BootSourceSelection fields, we have to select them from the subuery
                subquery.c.id,
                subquery.c.created,
                subquery.c.updated,
                subquery.c.os,
                subquery.c.arch,
                subquery.c.release,
                subquery.c.boot_source_id,
            )
            .select_from(subquery)
            .where(eq(subquery.c.rank, 1))
        )

        result = await self.execute_stmt(stmt)
        return [BootSourceSelection(**row._asdict()) for row in result]

    async def update_one(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    async def update_many(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    async def update_by_id(self, id, builder):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    async def _update(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )
