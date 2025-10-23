# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


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
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.events import EventsService

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
        configuration_service: ConfigurationsService,
        events_service: EventsService,
    ) -> None:
        super().__init__(context, repository)
        self.boot_source_cache_service = boot_source_cache_service
        self.boot_source_selections_service = boot_source_selections_service
        self.events_service = events_service
        self.configuration_service = configuration_service

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
        # cascade delete
        await self.boot_source_cache_service.delete_many(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.with_boot_source_id(
                    resource.id
                )
            )
        )
        await self.boot_source_selections_service.delete_many(
            query=QuerySpec(
                where=BootSourceSelectionClauseFactory.with_boot_source_id(
                    resource.id
                )
            )
        )

        await self.events_service.record_event(
            event_type=EventTypeEnum.BOOT_SOURCE,
            event_description=f"Deleted boot source {resource.url}",
        )
