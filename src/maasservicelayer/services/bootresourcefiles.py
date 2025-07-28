# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


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
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.services.base import BaseService, ServiceCache
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
        temporal_service: TemporalService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.temporal_service = temporal_service

    async def calculate_filename_on_disk(self, sha256: str) -> str:
        matching_resource = await self.get_one(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_sha256(sha256)
            )
        )
        if matching_resource:
            return matching_resource.filename_on_disk
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
