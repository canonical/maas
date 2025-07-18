# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheClauseFactory,
)
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionsRepository,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.services.base import BaseService, ServiceCache
from maasservicelayer.services.bootsourcecache import BootSourceCacheService


class BootSourceSelectionsService(
    BaseService[
        BootSourceSelection,
        BootSourceSelectionsRepository,
        BootSourceSelectionBuilder,
    ]
):
    def __init__(
        self,
        context: Context,
        repository: BootSourceSelectionsRepository,
        boot_source_cache_service: BootSourceCacheService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.boot_source_cache_service = boot_source_cache_service

    async def pre_create_hook(
        self, builder: BootSourceSelectionBuilder
    ) -> None:
        boot_source_id = builder.boot_source_id
        os = builder.os
        release = builder.release

        clauses = []

        if builder.arches and builder.arches != ["*"]:
            clauses += [
                BootSourceCacheClauseFactory.or_clauses(
                    [
                        BootSourceCacheClauseFactory.with_arch(arch)
                        for arch in builder.arches  # type: ignore
                    ]
                )
            ]

        if builder.subarches and builder.subarches != ["*"]:
            clauses += [
                BootSourceCacheClauseFactory.or_clauses(
                    [
                        BootSourceCacheClauseFactory.with_subarch(subarch)
                        for subarch in builder.subarches  # type: ignore
                    ]
                )
            ]

        if builder.labels and builder.labels != ["*"]:
            clauses += [
                BootSourceCacheClauseFactory.or_clauses(
                    [
                        BootSourceCacheClauseFactory.with_label(label)
                        for label in builder.labels  # type: ignore
                    ]
                )
            ]

        boot_source_cache = await self.boot_source_cache_service.exists(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.and_clauses(
                    [
                        BootSourceCacheClauseFactory.with_boot_source_id(
                            boot_source_id  # type: ignore
                        ),
                        BootSourceCacheClauseFactory.with_os(os),  # type: ignore
                        BootSourceCacheClauseFactory.with_release(release),  # type: ignore
                    ]
                    + clauses
                )
            )
        )

        if not boot_source_cache:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"{os}, {release} was not found in any available boot source.",
                    )
                ]
            )
