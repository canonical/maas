# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

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


class BootResourceService(
    BaseService[BootResource, BootResourcesRepository, BootResourceBuilder]
):
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
        self, resources: List[BootResource]
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
