# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the filesync LICENSE).

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.builders.bootresourcefilesync import (
    BootResourceFileSyncBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefilesync import (
    BootResourceFileSyncRepository,
)
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.models.bootresourcefilesync import BootResourceFileSync
from maasservicelayer.services.base import BaseService, ServiceCache
from maasservicelayer.services.nodes import NodesService


class BootResourceFileSyncService(
    BaseService[
        BootResourceFileSync,
        BootResourceFileSyncRepository,
        BootResourceFileSyncBuilder,
    ]
):
    def __init__(
        self,
        context: Context,
        repository: BootResourceFileSyncRepository,
        nodes_service: NodesService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.nodes_service = nodes_service

    async def get_regions_count(self) -> int:
        return len(
            await self.nodes_service.get_many(
                query=QuerySpec(
                    where=NodeClauseFactory.or_clauses(
                        [
                            NodeClauseFactory.with_type(
                                NodeTypeEnum.REGION_CONTROLLER
                            ),
                            NodeClauseFactory.with_type(
                                NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                            ),
                        ]
                    )
                )
            )
        )

    async def get_current_sync_size_for_files(self, file_ids: set[int]) -> int:
        return int(
            await self.repository.get_current_sync_size_for_files(file_ids)
        )

    async def get_synced_regions_for_file(self, file_id: int) -> list[str]:
        return await self.repository.get_synced_regions_for_file(file_id)
