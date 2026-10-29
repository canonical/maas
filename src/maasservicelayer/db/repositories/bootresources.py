# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import case, desc, func, Select, select, Table

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
    ImageStatus,
)
from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maasservicelayer.db.filters import SQLQuerySpec
from maasservicelayer.db.mappers.bootresources import (
    BootResourceDomainDataMapper,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    BootResourceFileSyncTable,
    BootResourceFileTable,
    BootResourceSetTable,
    BootResourceTable,
    NodeTable,
)
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootresources import (
    BootResource,
    CustomBootResourceStatistic,
    CustomBootResourceStatus,
)


class BootResourcesRepository(BaseRepository[BootResource]):
    def get_mapper(self) -> BootResourceDomainDataMapper:
        return BootResourceDomainDataMapper(BootResource, BootResourceTable)

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

        # Aggregate sync size across all regions per file
        file_sync_subq = (
            select(
                BootResourceFileSyncTable.c.file_id,
                func.sum(BootResourceFileSyncTable.c.size).label(
                    "total_synced"
                ),
            ).group_by(BootResourceFileSyncTable.c.file_id)
        ).subquery()

        sync_percentage_expr = (
            func.sum(file_sync_subq.c.total_synced)
            * 100.0
            / func.nullif(func.sum(BootResourceFileTable.c.size), 0)
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
                file_sync_subq,
                BootResourceFileTable.c.id == file_sync_subq.c.file_id,
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
        sql_query = self._translate(query) if query is not None else None
        stmt = self._custom_image_status_stmt()

        total_stmt = (
            select(func.count().label("total"))
            .select_from(BootResourceTable)
            .where(BootResourceTable.c.rtype == BootResourceType.UPLOADED)
        )
        if sql_query:
            total_stmt = SQLQuerySpec(where=sql_query.where).enrich_stmt(
                total_stmt
            )

        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = (
            stmt.order_by(desc(BootResourceTable.c.id))
            .offset((page - 1) * size)
            .limit(size)
        )
        if sql_query:
            stmt = sql_query.enrich_stmt(stmt)
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
        sql_query = self._translate(query) if query is not None else None
        total_stmt = (
            select(func.count().label("total"))
            .select_from(BootResourceTable)
            .where(BootResourceTable.c.rtype == BootResourceType.UPLOADED)
        )
        if sql_query:
            total_stmt = SQLQuerySpec(where=sql_query.where).enrich_stmt(
                total_stmt
            )

        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = self._custom_image_statistics_stmt()
        stmt = (
            stmt.order_by(desc(BootResourceTable.c.id))
            .offset((page - 1) * size)
            .limit(size)
        )
        if sql_query:
            stmt = sql_query.enrich_stmt(stmt)
        result = await self.execute_stmt(stmt)

        return ListResult(
            items=[
                CustomBootResourceStatistic(**row._asdict())
                for row in result.fetchall()
            ],
            total=total,
        )
