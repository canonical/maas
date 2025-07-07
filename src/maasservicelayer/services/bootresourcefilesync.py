# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the filesync LICENSE).

import math

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
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.bootresourcefilesync import BootResourceFileSync
from maasservicelayer.services.base import BaseService, ServiceCache
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
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
        bootresourcefiles_service: BootResourceFilesService,
        bootresourcesets_service: BootResourceSetsService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.nodes_service = nodes_service
        self.bootresourcefiles_service = bootresourcefiles_service
        self.bootresourcesets_service = bootresourcesets_service

    async def get_regions_count(self) -> int:
        return len(
            await self.nodes_service.get_many(
                query=QuerySpec(
                    where=NodeClauseFactory.and_clauses(
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
        return await self.repository.get_current_sync_size_for_files(file_ids)

    async def file_sync_progress(self, file_id: int) -> float:
        """Calculate the sync progress for a file.

        The process is the following:
            - get the size of the file
            - calculate the current size that is already synced
            - return the percentage of completion
        """
        file = await self.bootresourcefiles_service.get_by_id(file_id)
        if file is None:
            raise NotFoundException()

        n_regions = await self.get_regions_count()
        if n_regions == 0:
            return 0.0

        sync_size = await self.get_current_sync_size_for_files({file.id})

        return 100.0 * sync_size / (file.size * n_regions)

    async def resource_set_sync_progress(self, resource_set_id: int) -> float:
        """Calculate the sync progress for a resource set.

        The process is the following:
            - get all the files in the resource set
            - calculate the total size of the files
            - calculate the current size that is already synced
            - return the percentage of completion
        """
        resource_set = await self.bootresourcesets_service.get_by_id(
            resource_set_id
        )
        if not resource_set:
            raise NotFoundException()
        files = await self.bootresourcefiles_service.get_files_in_resource_set(
            resource_set_id
        )
        if not files:
            return 0.0

        n_regions = await self.get_regions_count()
        if n_regions == 0:
            return 0.0

        total_file_size = sum([f.size for f in files])

        sync_size = await self.get_current_sync_size_for_files(
            {f.id for f in files}
        )

        return 100.0 * sync_size / (total_file_size * n_regions)

    async def file_sync_complete(self, file_id: int) -> bool:
        sync_progress = await self.file_sync_progress(file_id)
        return math.isclose(sync_progress, 100.0)

    async def resource_set_sync_complete(self, resource_set_id: int) -> bool:
        sync_progress = await self.resource_set_sync_progress(resource_set_id)
        return math.isclose(sync_progress, 100.0)
