# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from typing import List, Sequence

import structlog

from maascommon.enums.events import EventTypeEnum
from maasservicelayer.builders.bootsources import BootSourceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheClauseFactory,
)
from maasservicelayer.db.repositories.bootsources import BootSourcesRepository
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
)
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
)
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.image_manifests import ImageManifestsService

logger = structlog.getLogger()


class BootSourcesService(
    BaseService[BootSource, BootSourcesRepository, BootSourceBuilder]
):
    resource_logging_name = "bootsource"

    def __init__(
        self,
        context: Context,
        repository: BootSourcesRepository,
        boot_source_cache_service: BootSourceCacheService,
        boot_source_selections_service: BootSourceSelectionsService,
        image_manifests_service: ImageManifestsService,
        events_service: EventsService,
    ) -> None:
        super().__init__(context, repository)
        self.boot_source_cache_service = boot_source_cache_service
        self.boot_source_selections_service = boot_source_selections_service
        self.events_service = events_service
        self.image_manifests_service = image_manifests_service

    async def _cascade_delete_dependents(
        self, resources: Sequence[BootSource]
    ) -> None:
        boot_source_ids = {resource.id for resource in resources}
        if not boot_source_ids:
            return

        await self.boot_source_cache_service.delete_many(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.with_boot_source_ids(
                    boot_source_ids
                )
            )
        )
        await self.boot_source_selections_service.delete_many(
            query=QuerySpec(
                where=BootSourceSelectionClauseFactory.with_boot_source_ids(
                    boot_source_ids
                )
            )
        )
        await self.image_manifests_service.delete_many(boot_source_ids)

    async def post_create_hook(self, resource: BootSource) -> None:
        await super().post_create_hook(resource)
        await self.events_service.record_event(
            event_type=EventTypeEnum.BOOT_SOURCE,
            event_description=f"Created boot source {resource.url}",
        )

    async def post_update_hook(
        self, old_resource: BootSource, updated_resource: BootSource
    ) -> None:
        if updated_resource.url != old_resource.url:
            description = f"Updated boot source url from {old_resource.url} to {updated_resource.url}"
        else:
            description = f"Updated boot source {updated_resource.url}"
        await self.events_service.record_event(
            event_type=EventTypeEnum.BOOT_SOURCE,
            event_description=description,
        )

    async def post_delete_hook(self, resource: BootSource) -> None:
        await self._cascade_delete_dependents([resource])
        await self.events_service.record_event(
            event_type=EventTypeEnum.BOOT_SOURCE,
            event_description=f"Deleted boot source {resource.url}",
        )

    async def post_delete_many_hook(self, resources: List[BootSource]) -> None:
        if not resources:
            return

        await self._cascade_delete_dependents(resources)
        for resource in resources:
            await self.events_service.record_event(
                event_type=EventTypeEnum.BOOT_SOURCE,
                event_description=f"Deleted boot source {resource.url}",
            )
