# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.events import EventTypeEnum
from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheClauseFactory,
)
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionsRepository,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.services.base import BaseService, ServiceCache
from maasservicelayer.services.bootresources import BootResourceService
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
        boot_resource_service: BootResourceService,
        events_service: EventsService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.events_service = events_service
        self.boot_source_cache_service = boot_source_cache_service
        self.boot_resource_service = boot_resource_service

    async def update_by_id(self, id, builder, etag_if_match=None):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    async def update_many(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    async def update_one(self, query, builder, etag_if_match=None):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    async def _update_resource(
        self, existing_resource, builder, etag_if_match=None
    ):
        raise NotImplementedError(
            "Update is not supported for bootsourceselections"
        )

    async def pre_create_hook(
        self, builder: BootSourceSelectionBuilder
    ) -> None:
        await self.ensure_boot_source_cache_exists(builder)

    async def post_create_hook(self, resource: BootSourceSelection) -> None:
        await self.events_service.record_event(
            event_type=EventTypeEnum.BOOT_SOURCE_SELECTION,
            event_description=f"Created boot source selection for "
            f"{resource.os}/{resource.release} "
            f"arch={resource.arch} "
            f"in boot source with ID {resource.boot_source_id}",
        )

    async def ensure_boot_source_cache_exists(
        self, builder: BootSourceSelectionBuilder
    ):
        boot_source_id = builder.ensure_set(builder.boot_source_id)
        os = builder.ensure_set(builder.os)
        release = builder.ensure_set(builder.release)
        arch = builder.ensure_set(builder.arch)

        boot_source_cache = await self.boot_source_cache_service.exists(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.and_clauses(
                    [
                        BootSourceCacheClauseFactory.with_boot_source_id(
                            boot_source_id
                        ),
                        BootSourceCacheClauseFactory.with_os(os),
                        BootSourceCacheClauseFactory.with_release(release),
                        BootSourceCacheClauseFactory.with_arch(arch),
                    ]
                )
            )
        )

        if not boot_source_cache:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"{os}, {release} was not found in any available boot source.",
                    )
                ]
            )

    async def create_without_boot_source_cache(
        self, builder: BootSourceSelectionBuilder
    ) -> BootSourceSelection:
        """Create a selection without checking if the boot source cache exists.

        NOTE: Only to use in the ImageSyncService. That is because when we create
        the boot source for the first time, we also want to add the selection for
        the commissioning release, but at this point we don't have anything in
        the boot source cache yet.

        See `ensure_boot_source_definition` in the ImageSyncService for the details.
        """
        return await self.repository.create(builder)

    async def pre_delete_hook(
        self, resource_to_be_deleted: BootSourceSelection
    ) -> None:
        await self.boot_resource_service.delete_many(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_selection_id(
                    resource_to_be_deleted.id
                )
            )
        )

    async def post_delete_hook(self, resource: BootSourceSelection) -> None:
        await self.events_service.record_event(
            event_type=EventTypeEnum.BOOT_SOURCE_SELECTION,
            event_description=f"Deleted boot source selection for "
            f"{resource.os}/{resource.release} "
            f"arch={resource.arch} "
            f"in boot source with ID {resource.boot_source_id}",
        )

    async def get_all_highest_priority(self) -> list[BootSourceSelection]:
        """Returns the selections with the highest priorities.

        This method will filter out all the duplicate selections and keep only
        the one with highest priority.

        E.g. if you have two selections that refer to the same os, arch, release,
        this method will return the one linked to the boot source with highest
        priority.
        """
        return await self.repository.get_all_highest_priority()
