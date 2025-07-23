# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.events import EventTypeEnum
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
from maasservicelayer.services.events import EventsService


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
        events_service: EventsService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.events_service = events_service
        self.boot_source_cache_service = boot_source_cache_service

    async def pre_create_hook(
        self, builder: BootSourceSelectionBuilder
    ) -> None:
        await self.ensure_boot_source_cache_exists(builder)
        await self.events_service.record_event(
            event_type=EventTypeEnum.BOOT_SOURCE_SELECTION,
            event_description=f"Updated boot source selection for "
            f"{builder.os}/{builder.release} "
            f"arches={builder.arches} "
            f"in boot source with ID {builder.boot_source_id}",
        )

    async def ensure_boot_source_cache_exists(
        self, builder: BootSourceSelectionBuilder
    ):
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

    async def post_update_hook(
        self,
        old_resource: BootSourceSelection,
        updated_resource: BootSourceSelection,
    ) -> None:
        await self.events_service.record_event(
            event_type=EventTypeEnum.BOOT_SOURCE_SELECTION,
            event_description=f"Updated boot source selection for "
            f"{updated_resource.os}/{updated_resource.release} "
            f"arches={updated_resource.arches} "
            f"in boot source with ID {updated_resource.boot_source_id}",
        )

    async def update_by_id(
        self,
        id: int,
        builder: BootSourceSelectionBuilder,
        etag_if_match: str | None = None,
    ):
        await self.ensure_boot_source_cache_exists(builder)
        return await super().update_by_id(id, builder, etag_if_match)

    async def post_delete_hook(self, resource: BootSourceSelection) -> None:
        await self.events_service.record_event(
            event_type=EventTypeEnum.BOOT_SOURCE_SELECTION,
            event_description=f"Updated boot source selection for "
            f"{resource.os}/{resource.release} "
            f"arches={resource.arches} "
            f"in boot source with ID {resource.boot_source_id}",
        )
