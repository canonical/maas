# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.bootsourcecache import BootSourceCacheBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheClauseFactory,
    BootSourceCacheRepository,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootsourcecache import BootSourceCache
from maasservicelayer.models.bootsources import (
    BootSourceAvailableImage,
    BootSourceCacheOSRelease,
)
from maasservicelayer.models.image_manifests import ImageManifest
from maasservicelayer.services.base import BaseService, ServiceCache


class BootSourceCacheService(
    BaseService[
        BootSourceCache, BootSourceCacheRepository, BootSourceCacheBuilder
    ]
):
    def __init__(
        self,
        context: Context,
        repository: BootSourceCacheRepository,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)

    async def create_or_update(
        self, builder: BootSourceCacheBuilder
    ) -> BootSourceCache:
        existing = await self.get_one(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.and_clauses(
                    [
                        BootSourceCacheClauseFactory.with_boot_source_id(
                            builder.ensure_set(builder.boot_source_id)
                        ),
                        BootSourceCacheClauseFactory.with_os(
                            builder.ensure_set(builder.os)
                        ),
                        BootSourceCacheClauseFactory.with_arch(
                            builder.ensure_set(builder.arch)
                        ),
                        BootSourceCacheClauseFactory.with_subarch(
                            builder.ensure_set(builder.subarch)
                        ),
                        BootSourceCacheClauseFactory.with_release(
                            builder.ensure_set(builder.release)
                        ),
                        BootSourceCacheClauseFactory.with_label(
                            builder.ensure_set(builder.label)
                        ),
                        BootSourceCacheClauseFactory.with_kflavor(
                            builder.ensure_set(builder.kflavor)
                        ),
                    ]
                )
            )
        )
        if existing:
            return await self._update_resource(existing, builder)
        return await self.create(builder)

    async def update_from_image_manifest(
        self, image_manifest: ImageManifest
    ) -> list[BootSourceCache]:
        """Update the boot source cache based on the image_manifest's manifest.

        Args:
            - image_manifest: the ImageManifest object to update from

        Returns:
            A list of the new boot source caches.
        """
        boot_source_caches: list[BootSourceCache] = []
        boot_source_cache_builders = set()
        for product_list in image_manifest.manifest:
            boot_source_cache_builders |= (
                BootSourceCacheBuilder.from_simplestreams_product_list(
                    product_list, image_manifest.boot_source_id
                )
            )

        for builder in boot_source_cache_builders:
            boot_source_caches.append(await self.create_or_update(builder))

        # delete the old boot source caches, i.e. the ones that weren't created
        # or updated.
        await self.delete_many(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.and_clauses(
                    [
                        BootSourceCacheClauseFactory.with_boot_source_id(
                            image_manifest.boot_source_id
                        ),
                        BootSourceCacheClauseFactory.not_clause(
                            BootSourceCacheClauseFactory.with_ids(
                                {cache.id for cache in boot_source_caches}
                            )
                        ),
                    ]
                )
            )
        )
        return boot_source_caches

    async def get_available_lts_releases(self) -> list[str]:
        return await self.repository.get_available_lts_releases()

    async def get_all_available_images(self) -> list[BootSourceAvailableImage]:
        return await self.repository.get_all_available_images()

    async def list_boot_source_cache_available_images(
        self,
        page: int,
        size: int,
        boot_source_id: int,
    ) -> ListResult[BootSourceAvailableImage]:
        return await self.repository.list_boot_source_cache_available_images(
            page=page, size=size, boot_source_id=boot_source_id
        )

    async def get_unique_os_releases(self) -> list[BootSourceCacheOSRelease]:
        return await self.repository.get_unique_os_releases()

    async def get_supported_arches(
        self, query: QuerySpec | None = None
    ) -> list[str]:
        return await self.repository.get_supported_arches(query=query)
