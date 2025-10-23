# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
    BootResourcesRepository,
)
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetClauseFactory,
)
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.services.base import BaseService, ServiceCache
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.simplestreams.models import Product
from maasservicelayer.utils.date import utcnow


class BootResourceService(
    BaseService[BootResource, BootResourcesRepository, BootResourceBuilder]
):
    resource_logging_name = "bootresources"

    def __init__(
        self,
        context: Context,
        repository: BootResourcesRepository,
        boot_resource_sets_service: BootResourceSetsService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.boot_resource_sets_service = boot_resource_sets_service

    async def pre_delete_hook(
        self, resource_to_be_deleted: BootResource
    ) -> None:
        await self.boot_resource_sets_service.delete_many(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_id(
                    resource_to_be_deleted.id
                )
            )
        )

    async def pre_delete_many_hook(
        self, resources: list[BootResource]
    ) -> None:
        await self.boot_resource_sets_service.delete_many(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_ids(
                    [r.id for r in resources]
                )
            )
        )

    async def create_or_update_from_simplestreams_product(
        self, product: Product
    ) -> BootResource:
        builder = BootResourceBuilder.from_simplestreams_product(product)
        boot_resource = await self.get_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_rtype(
                            builder.ensure_set(builder.rtype)
                        ),
                        BootResourceClauseFactory.with_name(
                            builder.ensure_set(builder.name)
                        ),
                        BootResourceClauseFactory.with_architecture(
                            builder.ensure_set(builder.architecture)
                        ),
                        BootResourceClauseFactory.with_alias(
                            builder.ensure_set(builder.alias)
                        ),
                    ]
                )
            ),
        )
        if boot_resource:
            boot_resource = await self._update_resource(boot_resource, builder)
            return boot_resource
        boot_resource = await self.create(builder)
        return boot_resource

    async def delete_all_without_sets(self) -> list[BootResource]:
        """Delete all the boot resources that don't have an associated resource set."""
        all_resource_sets = await self.boot_resource_sets_service.get_many(
            query=QuerySpec()
        )
        boot_resource_ids_with_sets = {
            rset.resource_id for rset in all_resource_sets
        }
        return await self.delete_many(
            query=QuerySpec(
                where=BootResourceClauseFactory.not_clause(
                    BootResourceClauseFactory.with_ids(
                        boot_resource_ids_with_sets
                    )
                )
            )
        )

    async def get_usable_architectures(self) -> list[str]:
        """Return the set of usable architectures.

        Return the architectures for which the resource has at least one
        commissioning image and at least one install image.
        """
        architectures: set[str] = set()

        all_boot_resources = await self.get_many(query=QuerySpec())
        for boot_resource in all_boot_resources:
            latest_resource_set = await self.boot_resource_sets_service.get_latest_complete_set_for_boot_resource(
                boot_resource.id
            )
            if not latest_resource_set:
                continue

            is_usable = await self.boot_resource_sets_service.is_usable(
                latest_resource_set.id
            )
            is_xinstallable = (
                await self.boot_resource_sets_service.is_xinstallable(
                    latest_resource_set.id
                )
            )
            if latest_resource_set and is_usable and is_xinstallable:
                if (
                    "hwe-" not in boot_resource.architecture
                    and "ga-" not in boot_resource.architecture
                ):
                    architectures.add(boot_resource.architecture)

                arch, _ = boot_resource.split_arch()

                if "subarches" in boot_resource.extra:
                    for subarch in boot_resource.extra["subarches"].split(","):
                        if "hwe-" not in subarch and "ga-" not in subarch:
                            architectures.add(f"{arch}/{subarch.strip()}")
                if "platform" in boot_resource.extra:
                    architectures.add(
                        f"{arch}/{boot_resource.extra['platform']}"
                    )
                if "supported_platforms" in boot_resource.extra:
                    for platform in boot_resource.extra[
                        "supported_platforms"
                    ].split(","):
                        architectures.add(f"{arch}/{platform}")

        return sorted(architectures)

    async def get_next_version_name(self, boot_resource_id: int) -> str:
        version_name = utcnow().strftime("%Y%m%d")

        sets_for_boot_resource = (
            await self.boot_resource_sets_service.get_many(
                query=QuerySpec(
                    where=BootResourceSetClauseFactory.and_clauses(
                        [
                            BootResourceSetClauseFactory.with_resource_id(
                                boot_resource_id
                            ),
                            BootResourceSetClauseFactory.with_version_prefix(
                                version_name
                            ),
                        ]
                    )
                ),
            )
        )
        if not sets_for_boot_resource:
            return version_name

        max_idx = 0
        for resource_set in sets_for_boot_resource:
            if "." in resource_set.version:
                _, set_idx = resource_set.version.split(".")
                set_idx = int(set_idx)
                if set_idx > max_idx:
                    max_idx = set_idx

        return "%s.%d" % (version_name, max_idx + 1)
