# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import List

from sqlalchemy import desc, func, Select, select, Table

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maascommon.enums.node import NodeStatus
from maasservicelayer.db.filters import SQLQuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ReadOnlyRepository,
)
from maasservicelayer.db.tables import (
    BootResourceFileTable,
    BootResourceSetTable,
    BootResourceTable,
    BootSourceSelectionStatusView,
    BootSourceSelectionTable,
    BootSourceTable,
    NodeTable,
)
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelection,
    BootSourceSelectionStatistic,
    BootSourceSelectionStatus,
)


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
            .where(eq(BootSourceTable.c.enabled, True))
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
                # TODO: MAASENG-5738 remove legacyselection_id
                subquery.c.legacyselection_id,
            )
            .select_from(subquery)
            .where(eq(subquery.c.rank, 1))
        )

        result = await self.execute_stmt(stmt)
        return [BootSourceSelection(**row._asdict()) for row in result]

    async def update_one(self, query: QuerySpec, builder):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    async def update_many(self, query: QuerySpec, builder):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    async def update_by_id(self, id, builder):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    async def _update(self, query: QuerySpec, builder):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    def _selection_statistics_stmt(self) -> Select:
        aggregated_subq = (
            select(
                BootResourceTable.c.selection_id.label("selection_id"),
                func.max(BootResourceTable.c.last_deployed).label(
                    "last_deployed"
                ),
                func.max(BootResourceTable.c.updated).label("last_updated"),
                func.sum(BootResourceFileTable.c.size).label("size"),
                # bool_or will return True if any of the files satisfy the condition
                func.bool_or(
                    BootResourceFileTable.c.filetype
                    == BootResourceFileType.SQUASHFS_IMAGE
                ).label("deploy_to_memory"),
            )
            .select_from(BootResourceTable)
            .join(
                BootResourceSetTable,
                BootResourceTable.c.id == BootResourceSetTable.c.resource_id,
            )
            .join(
                BootResourceFileTable,
                BootResourceFileTable.c.resource_set_id
                == BootResourceSetTable.c.id,
            )
            .where(
                BootResourceTable.c.rtype == BootResourceType.SYNCED,
                BootResourceTable.c.bootloader_type.is_(None),
            )
            .group_by(BootResourceTable.c.selection_id)
            .subquery()
        )

        node_count_subq = (
            select(
                BootSourceSelectionTable.c.id.label("selection_id"),
                func.count(NodeTable.c.id).label("node_count"),
            )
            .select_from(BootSourceSelectionTable)
            .join(
                NodeTable,
                (
                    (BootSourceSelectionTable.c.os == NodeTable.c.osystem)
                    & (
                        NodeTable.c.distro_series
                        == BootSourceSelectionTable.c.release
                    )
                    & (
                        func.substring(
                            NodeTable.c.architecture,
                            r"(\w+)/.*",
                        )
                        == BootSourceSelectionTable.c.arch
                    )
                ),
                isouter=True,
            )
            .where(
                NodeTable.c.status.in_(
                    [NodeStatus.DEPLOYED, NodeStatus.DEPLOYING]
                ),
            )
            .group_by(BootSourceSelectionTable.c.id)
            .subquery()
        )

        stmt = (
            select(
                BootSourceSelectionTable.c.id,
                func.coalesce(aggregated_subq.c.last_updated, None).label(
                    "last_updated"
                ),
                func.coalesce(aggregated_subq.c.last_deployed, None).label(
                    "last_deployed"
                ),
                func.coalesce(aggregated_subq.c.size, 0).label("size"),
                func.coalesce(aggregated_subq.c.deploy_to_memory, False).label(
                    "deploy_to_memory"
                ),
                func.coalesce(node_count_subq.c.node_count, 0).label(
                    "node_count"
                ),
            )
            .select_from(BootSourceSelectionTable)
            .join(
                aggregated_subq,
                aggregated_subq.c.selection_id
                == BootSourceSelectionTable.c.id,
                isouter=True,
            )
            .join(
                node_count_subq,
                node_count_subq.c.selection_id
                == BootSourceSelectionTable.c.id,
                isouter=True,
            )
        )
        return stmt

    async def get_selection_statistic_by_id(
        self, id: int
    ) -> BootSourceSelectionStatistic | None:
        stmt = self._selection_statistics_stmt()
        stmt = stmt.where(eq(BootSourceSelectionTable.c.id, id))
        result = (await self.execute_stmt(stmt)).one_or_none()

        if not result:
            return None

        return BootSourceSelectionStatistic(**result._asdict())

    async def list_selections_statistics(
        self, page: int, size: int, query: QuerySpec | None = None
    ) -> ListResult[BootSourceSelectionStatistic]:
        sql_query = self._translate(query) if query is not None else None
        total_stmt = select(func.count()).select_from(
            self.get_repository_table()
        )
        if sql_query:
            total_stmt = SQLQuerySpec(where=sql_query.where).enrich_stmt(
                total_stmt
            )
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = self._selection_statistics_stmt()
        stmt = (
            stmt.order_by(desc(BootSourceSelectionTable.c.id))
            .offset((page - 1) * size)
            .limit(size)
        )
        if sql_query:
            stmt = sql_query.enrich_stmt(stmt)

        result = await self.execute_stmt(stmt)
        return ListResult(
            items=[
                BootSourceSelectionStatistic(**row._asdict())
                for row in result.fetchall()
            ],
            total=total,
        )


class BootSourceSelectionStatusRepository(
    ReadOnlyRepository[BootSourceSelectionStatus]
):
    def get_repository_table(self) -> Table:
        return BootSourceSelectionStatusView

    def get_model_factory(self) -> type[BootSourceSelectionStatus]:
        return BootSourceSelectionStatus
