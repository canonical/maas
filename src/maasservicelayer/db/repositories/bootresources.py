# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Iterable

from sqlalchemy import case, desc, func, Select, select, Table

from maascommon.enums.boot_resources import BootResourceType, ImageStatus
from maasservicelayer.db.filters import (
    Clause,
    ClauseFactory,
    OrderByClause,
    OrderByClauseFactory,
    QuerySpec,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    BootResourceFileSyncTable,
    BootResourceFileTable,
    BootResourceSetTable,
    BootResourceTable,
    NodeTable,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootresources import (
    BootResource,
    CustomBootResourceStatus,
)


class BootResourceClauseFactory(ClauseFactory):
    @classmethod
    def with_name(cls, name: str) -> Clause:
        return Clause(condition=eq(BootResourceTable.c.name, name))

    @classmethod
    def with_names(cls, names: list[str]) -> Clause:
        return Clause(condition=BootResourceTable.c.name.in_(names))

    @classmethod
    def with_architecture(cls, architecture: str) -> Clause:
        return Clause(
            condition=eq(BootResourceTable.c.architecture, architecture)
        )

    @classmethod
    def with_architecture_starting_with(cls, partial_arch: str) -> Clause:
        return Clause(
            condition=BootResourceTable.c.architecture.startswith(partial_arch)
        )

    @classmethod
    def with_alias(cls, alias: str | None) -> Clause:
        return Clause(condition=eq(BootResourceTable.c.alias, alias))

    @classmethod
    def with_rtype(cls, rtype: BootResourceType) -> Clause:
        return Clause(condition=eq(BootResourceTable.c.rtype, rtype))

    @classmethod
    def with_ids(cls, ids: Iterable[int]) -> Clause:
        return Clause(condition=BootResourceTable.c.id.in_(ids))

    @classmethod
    def with_selection_id(cls, selection_id: int) -> Clause:
        return Clause(
            condition=eq(BootResourceTable.c.selection_id, selection_id)
        )

    @classmethod
    def with_selection_ids(cls, selection_ids: Iterable[int]) -> Clause:
        return Clause(
            condition=BootResourceTable.c.selection_id.in_(selection_ids)
        )


class BootResourceOrderByClauses(OrderByClauseFactory):
    @staticmethod
    def by_name_with_priority(lts_releases: list[str]) -> OrderByClause:
        return OrderByClause(
            column=case(
                {
                    release: priority
                    for priority, release in enumerate(lts_releases)
                },
                value=BootResourceTable.c.name,
            )
        )


class BootResourcesRepository(BaseRepository[BootResource]):
    def get_repository_table(self) -> Table:
        return BootResourceTable

    def get_model_factory(self) -> type[BootResource]:
        return BootResource

    def _custom_image_status_stmt(self) -> Select:
        sync_percentage_expr = (
            func.sum(BootResourceFileSyncTable.c.size)
            * 100
            / func.sum(BootResourceFileTable.c.size)
            / (
                select(func.count())
                .select_from(NodeTable)
                .where(NodeTable.c.node_type.in_([3, 4]))
                .scalar_subquery()
            )
        )

        stmt = (
            select(
                BootResourceTable.c.id,
                sync_percentage_expr.label("sync_percentage"),
                case(
                    (sync_percentage_expr == 100.0, ImageStatus.READY),
                    (
                        sync_percentage_expr == 0,
                        ImageStatus.WAITING_FOR_DOWNLOAD,
                    ),
                    else_=ImageStatus.DOWNLOADING,
                ).label("status"),
            )
            .select_from(BootResourceTable)
            .join(
                BootResourceSetTable,
                BootResourceTable.c.id == BootResourceSetTable.c.resource_id,
            )
            .join(
                BootResourceFileTable,
                BootResourceSetTable.c.id
                == BootResourceFileTable.c.resource_set_id,
            )
            .join(
                BootResourceFileSyncTable,
                BootResourceFileTable.c.id
                == BootResourceFileSyncTable.c.file_id,
            )
            .where(BootResourceTable.c.rtype == BootResourceType.UPLOADED)
            .group_by(
                BootResourceTable.c.id,
            )
        )
        return stmt

    async def get_custom_image_status_by_id(
        self, id: int
    ) -> CustomBootResourceStatus | None:
        stmt = self._custom_image_status_stmt()
        stmt = stmt.where(eq(BootResourceTable.c.id, id))
        result = (await self.execute_stmt(stmt)).one_or_none()

        if not result:
            return None

        return CustomBootResourceStatus(**result._asdict())

    async def list_custom_images_status(
        self, page: int, size: int, query: QuerySpec | None = None
    ) -> ListResult[CustomBootResourceStatus]:
        stmt = self._custom_image_status_stmt()

        total_stmt = (
            select(func.count().label("total"))
            .select_from(BootResourceTable)
            .where(BootResourceTable.c.rtype == BootResourceType.UPLOADED)
        )
        if query:
            total_stmt = query.enrich_stmt(total_stmt)

        total_result = await self.execute_stmt(total_stmt)
        total = total_result.scalar_one()

        stmt = (
            stmt.order_by(desc(BootResourceTable.c.id))
            .offset((page - 1) * size)
            .limit(size)
        )
        if query:
            stmt = query.enrich_stmt(stmt)
        result = await self.execute_stmt(stmt)

        return ListResult(
            items=[
                CustomBootResourceStatus(**row._asdict())
                for row in result.fetchall()
            ],
            total=total,
        )
