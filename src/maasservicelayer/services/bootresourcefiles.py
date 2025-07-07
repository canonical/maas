# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasservicelayer.builders.bootresourcefiles import BootResourceFileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefiles import (
    BootResourceFileClauseFactory,
    BootResourceFilesRepository,
)
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.services.base import BaseService, ServiceCache

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
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)

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

    async def get_files_in_resource_set(
        self, resource_set_id: int
    ) -> list[BootResourceFile]:
        return await self.repository.get_files_in_resource_set(resource_set_id)
