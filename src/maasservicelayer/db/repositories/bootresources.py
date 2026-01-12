# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Iterable

from sqlalchemy import case, desc, func, join, Select, select, Table

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
    ImageStatus,
)
from maascommon.enums.node import NodeStatus, NodeTypeEnum
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
    BootSourceSelectionTable,
    NodeTable,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootresources import (
    BootResource,
    CustomBootResourceStatistic,
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
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(BootResourceTable.c.id, id))

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

    @classmethod
    def with_bootloader_type(cls, bootloader_type: str | None) -> Clause:
        return Clause(
            condition=eq(BootResourceTable.c.bootloader_type, bootloader_type)
        )

    @classmethod
    def with_selection_boot_source_id(cls, boot_source_id: int) -> Clause:
        return Clause(
            condition=eq(
                BootSourceSelectionTable.c.boot_source_id, boot_source_id
            ),
            joins=[
                join(
                    BootSourceSelectionTable,
                    BootResourceTable,
                    eq(
                        BootSourceSelectionTable.c.id,
                        BootResourceTable.c.selection_id,
                    ),
                )
            ],
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
        node_count_subq = (
            select(func.count())
            .select_from(NodeTable)
            .where(
                NodeTable.c.node_type.in_(
                    [
                        NodeTypeEnum.REGION_CONTROLLER,
                        NodeTypeEnum.REGION_AND_RACK_CONTROLLER,
                    ]
                )
            )
            .scalar_subquery()
        )

        sync_percentage_expr = (
            func.sum(BootResourceFileSyncTable.c.size)
            * 100.0
            / func.sum(BootResourceFileTable.c.size)
            / node_count_subq
        )

        stmt = (
            select(
                BootResourceTable.c.id,
                func.coalesce(sync_percentage_expr, 0).label(
                    "sync_percentage"
                ),
                case(
                    (sync_percentage_expr == 100.0, ImageStatus.READY),
                    (sync_percentage_expr > 0, ImageStatus.DOWNLOADING),
                    else_=ImageStatus.WAITING_FOR_DOWNLOAD,
                ).label("status"),
            )
            .select_from(BootResourceTable)
            .join(
                BootResourceSetTable,
                BootResourceTable.c.id == BootResourceSetTable.c.resource_id,
                isouter=True,
            )
            .join(
                BootResourceFileTable,
                BootResourceSetTable.c.id
                == BootResourceFileTable.c.resource_set_id,
                isouter=True,
            )
            .join(
                BootResourceFileSyncTable,
                BootResourceFileTable.c.id
                == BootResourceFileSyncTable.c.file_id,
                isouter=True,
            )
            .where(BootResourceTable.c.rtype == BootResourceType.UPLOADED)
            .group_by(BootResourceTable.c.id)
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

        total = (await self.execute_stmt(total_stmt)).scalar_one()

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

    def _custom_image_statistics_stmt(self) -> Select:
        aggregated_subq = (
            select(
                BootResourceTable.c.id,
                BootResourceTable.c.updated.label("last_updated"),
                BootResourceTable.c.last_deployed.label("last_deployed"),
                func.sum(BootResourceFileTable.c.size).label("size"),
                # bool_or will return True if any of the files satisfy the condition
                func.bool_or(
                    BootResourceFileTable.c.filetype.in_(
                        [
                            BootResourceFileType.ROOT_TGZ,
                            BootResourceFileType.ROOT_TXZ,
                        ]
                    )
                ).label("deploy_to_memory"),
            )
            .select_from(BootResourceTable)
            .join(
                BootResourceSetTable,
                eq(BootResourceTable.c.id, BootResourceSetTable.c.resource_id),
            )
            .join(
                BootResourceFileTable,
                eq(
                    BootResourceFileTable.c.resource_set_id,
                    BootResourceSetTable.c.id,
                ),
            )
            .where(
                eq(BootResourceTable.c.rtype, BootResourceType.UPLOADED),
                BootResourceTable.c.bootloader_type.is_(None),
            )
            .group_by(BootResourceTable.c.id)
            .subquery()
        )

        node_count_subq = (
            select(
                BootResourceTable.c.id,
                func.count(NodeTable.c.id).label("node_count"),
            )
            .select_from(BootResourceTable)
            .join(
                NodeTable,
                (
                    # Boot resource name is in the format os/series
                    eq(
                        BootResourceTable.c.name,
                        (
                            NodeTable.c.osystem
                            + "/"
                            + NodeTable.c.distro_series
                        ),
                    )
                    &
                    # Only match the architecture and not the subarch
                    eq(
                        func.substring(NodeTable.c.architecture, r"(\w+)/.*"),
                        func.substring(
                            BootResourceTable.c.architecture, r"(\w+)/.*"
                        ),
                    )
                    & NodeTable.c.status.in_(
                        [NodeStatus.DEPLOYED, NodeStatus.DEPLOYING]
                    )
                ),
                isouter=True,
            )
            .where(
                eq(BootResourceTable.c.rtype, BootResourceType.UPLOADED),
                BootResourceTable.c.bootloader_type.is_(None),
            )
            .group_by(BootResourceTable.c.id)
            .subquery()
        )

        stmt = (
            select(
                BootResourceTable.c.id,
                aggregated_subq.c.last_updated,
                aggregated_subq.c.last_deployed,
                aggregated_subq.c.size,
                aggregated_subq.c.deploy_to_memory,
                func.coalesce(node_count_subq.c.node_count, 0).label(
                    "node_count"
                ),
            )
            .select_from(BootResourceTable)
            .join(
                aggregated_subq,
                eq(aggregated_subq.c.id, BootResourceTable.c.id),
                isouter=True,
            )
            .join(
                node_count_subq,
                eq(node_count_subq.c.id, BootResourceTable.c.id),
                isouter=True,
            )
            .where(
                eq(BootResourceTable.c.rtype, BootResourceType.UPLOADED),
                BootResourceTable.c.bootloader_type.is_(None),
            )
        )
        return stmt

    async def get_custom_image_statistic_by_id(
        self, id: int
    ) -> CustomBootResourceStatistic | None:
        stmt = self._custom_image_statistics_stmt()
        stmt = stmt.where(eq(BootResourceTable.c.id, id))
        result = (await self.execute_stmt(stmt)).one_or_none()

        if not result:
            return None

        return CustomBootResourceStatistic(**result._asdict())

    async def list_custom_images_statistics(
        self, page: int, size: int, query: QuerySpec | None = None
    ) -> ListResult[CustomBootResourceStatistic]:
        total_stmt = (
            select(func.count().label("total"))
            .select_from(BootResourceTable)
            .where(BootResourceTable.c.rtype == BootResourceType.UPLOADED)
        )
        if query:
            total_stmt = query.enrich_stmt(total_stmt)

        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = self._custom_image_statistics_stmt()
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
                CustomBootResourceStatistic(**row._asdict())
                for row in result.fetchall()
            ],
            total=total,
        )
