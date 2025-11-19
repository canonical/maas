# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import math
from typing import List

from maascommon.enums.boot_resources import BootResourceFileType
from maasservicelayer.builders.bootresourcesets import BootResourceSetBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefiles import (
    BootResourceFileClauseFactory,
)
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetClauseFactory,
    BootResourceSetsRepository,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.services.base import BaseService, ServiceCache
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresourcefilesync import (
    BootResourceFileSyncService,
)
from maasservicelayer.simplestreams.models import Product

# `BootResourceSet` must contain at least one of the file types to be consider
# as supporting the ability to xinstall. 'xinstall' being the
# fastpath-installer.
XINSTALL_TYPES = (
    BootResourceFileType.SQUASHFS_IMAGE,
    BootResourceFileType.ROOT_IMAGE,
    BootResourceFileType.ROOT_TGZ,
    BootResourceFileType.ROOT_TBZ,
    BootResourceFileType.ROOT_TXZ,
    BootResourceFileType.ROOT_DD,
)


class BootResourceSetsService(
    BaseService[
        BootResourceSet, BootResourceSetsRepository, BootResourceSetBuilder
    ]
):
    def __init__(
        self,
        context: Context,
        repository: BootResourceSetsRepository,
        boot_resource_files_service: BootResourceFilesService,
        boot_resource_file_sync_service: BootResourceFileSyncService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.boot_resource_file_sync_service = boot_resource_file_sync_service
        self.boot_resource_files_service = boot_resource_files_service

    async def pre_delete_hook(
        self, resource_to_be_deleted: BootResourceSet
    ) -> None:
        await self.boot_resource_files_service.delete_many(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_resource_set_id(
                    resource_to_be_deleted.id
                )
            )
        )

    async def pre_delete_many_hook(
        self, resources: List[BootResourceSet]
    ) -> None:
        await self.boot_resource_files_service.delete_many(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_resource_set_ids(
                    [r.id for r in resources]
                )
            )
        )

    async def get_latest_for_boot_resource(
        self, boot_resource_id: int
    ) -> BootResourceSet | None:
        return await self.repository.get_latest_for_boot_resource(
            boot_resource_id
        )

    async def get_latest_complete_set_for_boot_resource(
        self,
        boot_resource_id: int,
    ) -> BootResourceSet | None:
        resource_sets = (
            await self.repository.get_many_newest_to_oldest_for_boot_resource(
                boot_resource_id
            )
        )

        num_regions = (
            await self.boot_resource_file_sync_service.get_regions_count()
        )

        for resource_set in resource_sets:
            files_in_resource_set = await self.boot_resource_files_service.get_files_in_resource_set(
                resource_set.id
            )
            if len(files_in_resource_set) == 0:
                continue

            files_size = sum([f.size for f in files_in_resource_set])
            sync_size = await self.boot_resource_file_sync_service.get_current_sync_size_for_files(
                set([f.id for f in files_in_resource_set])
            )
            if sync_size != num_regions * files_size:
                continue

            return resource_set
        return None

    async def get_or_create_from_simplestreams_product(
        self, product: Product, boot_resource_id: int
    ) -> BootResourceSet:
        latest_version = product.get_latest_version().version_name
        builder = BootResourceSetBuilder(
            # TODO: user-provided version
            version=latest_version,
            label=product.label,
            resource_id=boot_resource_id,
        )
        resource_set, _ = await self.get_or_create(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.and_clauses(
                    [
                        BootResourceSetClauseFactory.with_resource_id(
                            boot_resource_id
                        ),
                        BootResourceSetClauseFactory.with_version(
                            latest_version
                        ),
                        BootResourceSetClauseFactory.with_label(product.label),
                    ]
                )
            ),
            builder=builder,
        )
        return resource_set

    async def get_sync_progress(self, resource_set_id: int) -> float:
        """Calculate the sync progress for a resource set.

        The process is the following:
            - get all the files in the resource set
            - calculate the total size of the files
            - calculate the current size that is already synced
            - return the percentage of completion
        """
        resource_set = await self.get_by_id(resource_set_id)
        if not resource_set:
            raise NotFoundException()
        files = (
            await self.boot_resource_files_service.get_files_in_resource_set(
                resource_set_id
            )
        )
        if not files:
            return 0.0

        n_regions = (
            await self.boot_resource_file_sync_service.get_regions_count()
        )

        total_file_size = sum([f.size for f in files])

        sync_size = await self.boot_resource_file_sync_service.get_current_sync_size_for_files(
            {f.id for f in files}
        )

        return 100.0 * sync_size / (total_file_size * n_regions)

    async def is_sync_complete(self, resource_set_id: int) -> bool:
        sync_progress = await self.get_sync_progress(resource_set_id)
        return math.isclose(sync_progress, 100.0)

    async def is_usable(self, resource_set_id: int) -> bool:
        """True if `BootResourceSet` contains all the required files."""
        files = (
            await self.boot_resource_files_service.get_files_in_resource_set(
                resource_set_id
            )
        )
        types = {file.filetype for file in files}
        return (
            BootResourceFileType.BOOT_KERNEL in types
            and BootResourceFileType.BOOT_INITRD in types
            and (
                BootResourceFileType.SQUASHFS_IMAGE in types
                or BootResourceFileType.ROOT_IMAGE in types
            )
        )

    async def is_xinstallable(self, resource_set_id: int) -> bool:
        associated_files = (
            await self.boot_resource_files_service.get_files_in_resource_set(
                resource_set_id
            )
        )
        return any(
            associated_file.filetype in XINSTALL_TYPES
            for associated_file in associated_files
        )
