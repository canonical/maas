# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict
from typing import List, Sequence

from maascommon.enums.events import EventTypeEnum
from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.builders.legacybootsourceselections import (
    LegacyBootSourceSelectionBuilder,
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
    BootSourceSelectionClauseFactory,
    BootSourceSelectionsRepository,
    BootSourceSelectionStatusRepository,
)
from maasservicelayer.db.repositories.legacybootsourceselections import (
    LegacyBootSourceSelectionClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelection,
    BootSourceSelectionStatus,
)
from maasservicelayer.services.base import (
    BaseService,
    ReadOnlyService,
    ServiceCache,
)
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.legacybootsourceselections import (
    LegacyBootSourceSelectionService,
)


class BootSourceSelectionStatusService(
    ReadOnlyService[
        BootSourceSelectionStatus,
        BootSourceSelectionStatusRepository,
    ]
): ...


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
        legacy_boot_source_selection_service: LegacyBootSourceSelectionService,
        events_service: EventsService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.events_service = events_service
        self.boot_source_cache_service = boot_source_cache_service
        self.boot_resource_service = boot_resource_service
        # TODO: MAASENG-5738 remove this
        self.legacy_boot_source_selection_service = (
            legacy_boot_source_selection_service
        )

    async def _delete_related_boot_resources(
        self, selections: Sequence[BootSourceSelection]
    ) -> None:
        selection_ids = {selection.id for selection in selections}
        if not selection_ids:
            return
        await self.boot_resource_service.delete_many(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_selection_ids(
                    selection_ids
                )
            )
        )

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
        await self._ensure_legacy_selection_exists(builder)

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

    # TODO: MAASENG-5738 remove this
    async def _ensure_legacy_selection_exists(
        self, builder: BootSourceSelectionBuilder
    ) -> None:
        legacy_selection = await self.legacy_boot_source_selection_service.get_one(
            query=QuerySpec(
                where=LegacyBootSourceSelectionClauseFactory.and_clauses(
                    [
                        LegacyBootSourceSelectionClauseFactory.with_os(
                            builder.ensure_set(builder.os)
                        ),
                        LegacyBootSourceSelectionClauseFactory.with_release(
                            builder.ensure_set(builder.release)
                        ),
                        LegacyBootSourceSelectionClauseFactory.with_boot_source_id(
                            builder.ensure_set(builder.boot_source_id)
                        ),
                    ]
                )
            )
        )
        arch = builder.ensure_set(builder.arch)
        if legacy_selection:
            # update arches if necessary
            if (
                arch not in legacy_selection.arches
                and legacy_selection.arches != ["*"]
            ):
                await self.legacy_boot_source_selection_service.update_by_id(
                    id=legacy_selection.id,
                    builder=LegacyBootSourceSelectionBuilder(
                        arches=legacy_selection.arches + [arch]
                    ),
                )
        else:
            legacy_selection = (
                await self.legacy_boot_source_selection_service.create(
                    builder=LegacyBootSourceSelectionBuilder(
                        os=builder.ensure_set(builder.os),
                        release=builder.ensure_set(builder.release),
                        boot_source_id=builder.ensure_set(
                            builder.boot_source_id
                        ),
                        arches=[arch],
                        subarches=["*"],
                        labels=["*"],
                    ),
                )
            )
        builder.legacyselection_id = legacy_selection.id

    # TODO: MAASENG-5738 remove this
    async def _update_legacy_selection_after_deletion(
        self, resources: list[BootSourceSelection]
    ) -> None:
        legacy_selection_ids = set()
        arches_to_remove = defaultdict(list)
        for res in resources:
            legacy_selection_ids.add(res.legacyselection_id)
            arches_to_remove[res.legacyselection_id].append(res.arch)

        legacy_selections = (
            await self.legacy_boot_source_selection_service.get_many(
                query=QuerySpec(
                    where=LegacyBootSourceSelectionClauseFactory.with_ids(
                        legacy_selection_ids
                    )
                )
            )
        )

        for legacy_sel in legacy_selections:
            if legacy_sel.arches == ["*"]:
                if not await self.exists(
                    QuerySpec(
                        where=BootSourceSelectionClauseFactory.with_legacyselection_id(
                            legacy_sel.id
                        ),
                    )
                ):
                    # all the related selections have been deleted
                    await (
                        self.legacy_boot_source_selection_service.delete_by_id(
                            id=legacy_sel.id
                        )
                    )
                continue

            updated_arches = [
                arch
                for arch in legacy_sel.arches
                if arch not in arches_to_remove[legacy_sel.id]
            ]
            if not updated_arches:
                # If no arches are left, delete the legacy selection
                await self.legacy_boot_source_selection_service.delete_by_id(
                    id=legacy_sel.id
                )
            else:
                await self.legacy_boot_source_selection_service.update_by_id(
                    id=legacy_sel.id,
                    builder=LegacyBootSourceSelectionBuilder(
                        arches=updated_arches
                    ),
                )

    # TODO: MAASENG-5738 remove this
    async def ensure_selections_from_legacy(self):
        """Ensure that legacy selections have the corresponding new selections."""
        legacy_selections = (
            await self.legacy_boot_source_selection_service.get_many(
                query=QuerySpec()
            )
        )
        for legacy_selection in legacy_selections:
            if legacy_selection.arches == ["*"]:
                arches = await self.boot_source_cache_service.get_supported_arches(
                    query=QuerySpec(
                        where=BootSourceCacheClauseFactory.and_clauses(
                            [
                                BootSourceCacheClauseFactory.with_os(
                                    legacy_selection.os
                                ),
                                BootSourceCacheClauseFactory.with_release(
                                    legacy_selection.release
                                ),
                                BootSourceCacheClauseFactory.with_boot_source_id(
                                    legacy_selection.boot_source_id
                                ),
                            ]
                        )
                    )
                )
            else:
                arches = legacy_selection.arches
            for arch in arches:
                builder = BootSourceSelectionBuilder(
                    os=legacy_selection.os,
                    release=legacy_selection.release,
                    arch=arch,
                    boot_source_id=legacy_selection.boot_source_id,
                    legacyselection_id=legacy_selection.id,
                )
                if not await self.exists(
                    query=QuerySpec(
                        where=BootSourceSelectionClauseFactory.and_clauses(
                            [
                                BootSourceSelectionClauseFactory.with_os(
                                    legacy_selection.os
                                ),
                                BootSourceSelectionClauseFactory.with_release(
                                    legacy_selection.release
                                ),
                                BootSourceSelectionClauseFactory.with_arch(
                                    arch
                                ),
                                BootSourceSelectionClauseFactory.with_boot_source_id(
                                    legacy_selection.boot_source_id
                                ),
                            ]
                        )
                    )
                ):
                    await self.create(builder=builder)

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
        # TODO: MAASENG-5738 remove this
        await self._ensure_legacy_selection_exists(builder)
        return await self.repository.create(builder)

    async def _create_event_for_deletion(
        self, resource: BootSourceSelection
    ) -> None:
        await self.events_service.record_event(
            event_type=EventTypeEnum.BOOT_SOURCE_SELECTION,
            event_description=f"Deleted boot source selection for "
            f"{resource.os}/{resource.release} "
            f"arch={resource.arch} "
            f"in boot source with ID {resource.boot_source_id}",
        )

    async def pre_delete_hook(
        self, resource_to_be_deleted: BootSourceSelection
    ) -> None:
        await self._delete_related_boot_resources([resource_to_be_deleted])

    async def pre_delete_many_hook(
        self, resources: List[BootSourceSelection]
    ) -> None:
        await self._delete_related_boot_resources(resources)

    async def post_delete_many_hook(
        self, resources: List[BootSourceSelection]
    ) -> None:
        """FIXME: We iterate over each resource because events bulk creation is
        not yet supported."""
        await self._update_legacy_selection_after_deletion(resources)
        for resource in resources:
            await self._create_event_for_deletion(resource)

    async def post_delete_hook(self, resource: BootSourceSelection) -> None:
        await self._create_event_for_deletion(resource)
        await self._update_legacy_selection_after_deletion([resource])

    async def get_all_highest_priority(self) -> list[BootSourceSelection]:
        """Returns the selections with the highest priorities.

        This method will filter out all the duplicate selections and keep only
        the one with highest priority.

        E.g. if you have two selections that refer to the same os, arch, release,
        this method will return the one linked to the boot source with highest
        priority.
        """
        return await self.repository.get_all_highest_priority()
