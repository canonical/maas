# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from typing import List

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
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.services.base import BaseService, ServiceCache
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.simplestreams.models import Product


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
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
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

    async def get_or_create_from_simplestreams_product(
        self, product: Product, boot_resource_id: int
    ) -> tuple[BootResourceSet, bool]:
        builder = BootResourceSetBuilder(
            # TODO: user-provided version
            version=product.get_latest_version().version_name,
            label=product.label,
            resource_id=boot_resource_id,
        )
        return await self.get_or_create(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.and_clauses(
                    [
                        BootResourceSetClauseFactory.with_resource_id(
                            boot_resource_id
                        ),
                        BootResourceSetClauseFactory.with_version(
                            product.get_latest_version().version_name
                        ),
                        BootResourceSetClauseFactory.with_label(product.label),
                    ]
                )
            ),
            builder=builder,
        )
