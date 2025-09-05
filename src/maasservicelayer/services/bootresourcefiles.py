# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import math

from maascommon.workflows.bootresource import (
    DELETE_BOOTRESOURCE_WORKFLOW_NAME,
    merge_resource_delete_param,
    ResourceDeleteParam,
    ResourceIdentifier,
)
from maasservicelayer.builders.bootresourcefiles import BootResourceFileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefiles import (
    BootResourceFileClauseFactory,
    BootResourceFilesRepository,
)
from maasservicelayer.db.repositories.bootresourcefilesync import (
    BootResourceFileSyncClauseFactory,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.services.base import BaseService, ServiceCache
from maasservicelayer.services.bootresourcefilesync import (
    BootResourceFileSyncService,
)
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.simplestreams.models import DownloadableFile

SHORTSHA256_MIN_PREFIX_LEN = 7


class BootResourceFilesService(
    BaseService[
        BootResourceFile, BootResourceFilesRepository, BootResourceFileBuilder
    ]
):
    def __init__(
        self,
        context: Context,
        repository: BootResourceFilesRepository,
        boot_resource_file_sync_service: BootResourceFileSyncService,
        temporal_service: TemporalService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.boot_resource_file_sync_service = boot_resource_file_sync_service
        self.temporal_service = temporal_service

    async def calculate_filename_on_disk(self, sha256: str) -> str:
        # there can be multiple files with the same sha256, so we can't use get_one
        matching_resources = await self.get_many(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_sha256(sha256)
            )
        )
        if matching_resources:
            return matching_resources[0].filename_on_disk
        collisions = await self.get_many(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_sha256_starting_with(
                    sha256[:SHORTSHA256_MIN_PREFIX_LEN]
                )
            )
        )
        if len(collisions) > 0:
            # Keep adding chars until we don't have a collision. We are going to find a suitable prefix here since we
            # have already excluded that there is an image with the same full sha.
            for i in range(SHORTSHA256_MIN_PREFIX_LEN + 1, 64):
                sha = sha256[:i]
                if all(
                    not f.filename_on_disk.startswith(sha) for f in collisions
                ):
                    return sha
            return sha256
        else:
            return sha256[:SHORTSHA256_MIN_PREFIX_LEN]

    async def post_delete_hook(self, resource: BootResourceFile) -> None:
        """
        At this point we already deleted the file from db, so we are checking
        if this was the last file with this exact sha256. If that's the case,
        we delete the file from disk.
        """
        if not await self.exists(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_sha256(
                    resource.sha256
                )
            )
        ):
            self.temporal_service.register_or_update_workflow_call(
                DELETE_BOOTRESOURCE_WORKFLOW_NAME,
                parameter=ResourceDeleteParam(
                    files=[
                        ResourceIdentifier(
                            sha256=resource.sha256,
                            filename_on_disk=resource.filename_on_disk,
                        )
                    ]
                ),
                parameter_merge_func=merge_resource_delete_param,
            )

    async def post_delete_many_hook(
        self, resources: list[BootResourceFile]
    ) -> None:
        """
        Same as `post_delete_hook` but for multiple BootResourceFile.
        """
        still_exist = await self.get_many(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_sha256_in(
                    [r.sha256 for r in resources]
                )
            )
        )
        to_delete = [
            r
            for r in resources
            if r.sha256 not in [s.sha256 for s in still_exist]
        ]

        if to_delete:
            resource_idents = [
                ResourceIdentifier(
                    sha256=r.sha256, filename_on_disk=r.filename_on_disk
                )
                for r in to_delete
            ]
            self.temporal_service.register_or_update_workflow_call(
                DELETE_BOOTRESOURCE_WORKFLOW_NAME,
                parameter=ResourceDeleteParam(files=resource_idents),
                parameter_merge_func=merge_resource_delete_param,
            )

    async def get_files_in_resource_set(
        self, resource_set_id: int
    ) -> list[BootResourceFile]:
        return await self.repository.get_files_in_resource_set(resource_set_id)

    async def get_or_create_from_simplestreams_file(
        self, file: DownloadableFile, resource_set_id: int
    ) -> BootResourceFile:
        filename_on_disk = await self.calculate_filename_on_disk(file.sha256)
        builder = BootResourceFileBuilder.from_simplestreams_file(
            file, resource_set_id
        )
        builder.filename_on_disk = filename_on_disk

        resource_file = await self.get_one(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.and_clauses(
                    [
                        BootResourceFileClauseFactory.with_resource_set_id(
                            resource_set_id
                        ),
                        BootResourceFileClauseFactory.with_filename(
                            builder.ensure_set(builder.filename)
                        ),
                    ]
                )
            ),
        )
        if not resource_file:
            return await self.create(builder)
        if resource_file.sha256 != file.sha256:
            # We can have an hash mismatch when the file in the mirror comes from
            # an image that has been updated to a newer version.
            # In this case, we delete the file (to also remove it from disk)
            # and create a new one
            await self._delete_resource(resource_file)
            resource_file = await self.create(builder)
        return resource_file

    async def pre_delete_hook(
        self, resource_to_be_deleted: BootResourceFile
    ) -> None:
        await self.boot_resource_file_sync_service.delete_many(
            query=QuerySpec(
                where=BootResourceFileSyncClauseFactory.with_file_id(
                    resource_to_be_deleted.id
                )
            )
        )

    async def pre_delete_many_hook(
        self, resources: list[BootResourceFile]
    ) -> None:
        await self.boot_resource_file_sync_service.delete_many(
            query=QuerySpec(
                where=BootResourceFileSyncClauseFactory.with_file_ids(
                    {file.id for file in resources}
                )
            )
        )

    async def get_sync_progress(self, file_id: int) -> float:
        """Calculate the sync progress for a file.

        The process is the following:
            - get the size of the file
            - calculate the current size that is already synced
            - return the percentage of completion
        """
        file = await self.get_by_id(file_id)
        if file is None:
            raise NotFoundException()

        n_regions = (
            await self.boot_resource_file_sync_service.get_regions_count()
        )

        sync_size = await self.boot_resource_file_sync_service.get_current_sync_size_for_files(
            {file.id}
        )

        return 100.0 * sync_size / (file.size * n_regions)

    async def is_sync_complete(self, file_id: int) -> bool:
        sync_progress = await self.get_sync_progress(file_id)
        return math.isclose(sync_progress, 100.0)
