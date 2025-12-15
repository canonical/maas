# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maascommon.enums.boot_resources import ImageStatus, ImageUpdateStatus
from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.builders.legacybootsourceselections import (
    LegacyBootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionsRepository,
    BootSourceSelectionStatusRepository,
)
from maasservicelayer.exceptions.catalog import BadRequestException
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelection,
    BootSourceSelectionStatus,
)
from maasservicelayer.models.legacybootsourceselections import (
    LegacyBootSourceSelection,
)
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
    BootSourceSelectionStatusService,
)
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.legacybootsourceselections import (
    LegacyBootSourceSelectionService,
)
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import (
    ReadOnlyServiceCommonTests,
    ServiceCommonTests,
)


@pytest.mark.asyncio
class TestCommonBootSourceSelectionsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootSourceSelectionsService:
        return BootSourceSelectionsService(
            context=Context(),
            repository=Mock(BootSourceSelectionsRepository),
            boot_source_cache_service=Mock(BootSourceCacheService),
            boot_resource_service=Mock(BootResourceService),
            legacy_boot_source_selection_service=Mock(
                LegacyBootSourceSelectionService
            ),
            events_service=Mock(EventsService),
        )

    @pytest.fixture
    def test_instance(self) -> BootSourceSelection:
        now = utcnow()
        return BootSourceSelection(
            id=1,
            created=now,
            updated=now,
            os="ubuntu",
            release="noble",
            arch="amd64",
            boot_source_id=1,
            legacyselection_id=10,
        )

    @pytest.fixture
    def builder_model(self) -> type[BootSourceSelectionBuilder]:
        return BootSourceSelectionBuilder

    async def test_create(
        self, service_instance, test_instance, builder_model
    ):
        service_instance.repository.create.return_value = test_instance
        service_instance._ensure_legacy_selection_exists = AsyncMock()
        builder = BootSourceSelectionBuilder(
            os="ubuntu",
            release="jammy",
            arch="amd64",
            boot_source_id=1,
            legacyselection_id=10,
        )
        obj = await service_instance.create(builder)
        assert obj == test_instance
        service_instance.repository.create.assert_awaited_once_with(
            builder=builder
        )

    async def test_create_with_available_boot_resource(
        self, service_instance, test_instance, builder_model
    ):
        service_instance.boot_source_cache_service.exists.return_value = True
        service_instance._ensure_legacy_selection_exists = AsyncMock()
        await self.test_create(service_instance, test_instance, builder_model)

    async def test_create_with_inexistent_boot_resource(
        self, service_instance, test_instance, builder_model
    ):
        service_instance.boot_source_cache_service.exists.return_value = False
        service_instance._ensure_legacy_selection_exists = AsyncMock()
        with pytest.raises(BadRequestException):
            await self.test_create(
                service_instance, test_instance, builder_model
            )

    async def test_create_without_boot_source_cache(
        self, service_instance, builder_model
    ) -> None:
        service_instance._ensure_legacy_selection_exists = AsyncMock()
        await service_instance.create_without_boot_source_cache(
            builder_model()
        )
        service_instance.repository.create.assert_awaited_once_with(
            builder_model()
        )

    async def test_update_many(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_many(
                service_instance, test_instance, builder_model
            )

    async def test_update_one(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one(
                service_instance, test_instance, builder_model
            )

    async def test_update_one_not_found(self, service_instance, builder_model):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_not_found(
                service_instance, builder_model
            )

    async def test_update_one_etag_match(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_etag_match(
                service_instance, test_instance, builder_model
            )

    async def test_update_one_etag_not_matching(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_etag_not_matching(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id_not_found(
        self, service_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_not_found(
                service_instance, builder_model
            )

    async def test_update_by_id_etag_match(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_etag_match(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id_etag_not_matching(
        self, service_instance, test_instance, builder_model
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_etag_not_matching(
                service_instance, test_instance, builder_model
            )


@pytest.mark.asyncio
class TestBootSourceSelectionsService:
    @pytest.fixture
    def service(self) -> BootSourceSelectionsService:
        return BootSourceSelectionsService(
            context=Context(),
            repository=Mock(BootSourceSelectionsRepository),
            boot_source_cache_service=Mock(BootSourceCacheService),
            boot_resource_service=Mock(BootResourceService),
            legacy_boot_source_selection_service=Mock(
                LegacyBootSourceSelectionService
            ),
            events_service=Mock(EventsService),
        )

    @pytest.fixture
    def legacy_selection(self) -> LegacyBootSourceSelection:
        now = utcnow()
        return LegacyBootSourceSelection(
            id=10,
            created=now,
            updated=now,
            os="ubuntu",
            release="noble",
            arches=["amd64"],
            subarches=["*"],
            labels=["*"],
            boot_source_id=1,
        )

    @pytest.fixture
    def selection_builder(self) -> BootSourceSelectionBuilder:
        return BootSourceSelectionBuilder(
            os="ubuntu",
            release="noble",
            arch="amd64",
            boot_source_id=1,
        )

    @pytest.fixture
    def selection(self) -> BootSourceSelection:
        now = utcnow()
        return BootSourceSelection(
            id=1,
            created=now,
            updated=now,
            os="ubuntu",
            release="noble",
            arch="amd64",
            boot_source_id=1,
            legacyselection_id=10,
        )

    async def test_get_all_highest_priority(
        self, service: BootSourceSelectionsService
    ) -> None:
        await service.get_all_highest_priority()
        service.repository.get_all_highest_priority.assert_awaited_once()

    # TODO: MAASENG-5738 remove this
    async def test_ensure_legacy_selection_exists__create_new(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
        selection_builder: BootSourceSelectionBuilder,
    ) -> None:
        service.legacy_boot_source_selection_service.get_one.return_value = (
            None
        )
        service.legacy_boot_source_selection_service.create.return_value = (
            legacy_selection
        )

        await service._ensure_legacy_selection_exists(selection_builder)
        service.legacy_boot_source_selection_service.get_one.assert_awaited_once()
        service.legacy_boot_source_selection_service.create.assert_awaited_once_with(
            builder=LegacyBootSourceSelectionBuilder(
                os=selection_builder.os,
                release=selection_builder.release,
                arches=[selection_builder.arch],
                subarches=["*"],
                labels=["*"],
                boot_source_id=selection_builder.boot_source_id,
            )
        )
        assert selection_builder.legacyselection_id == legacy_selection.id

    async def test_ensure_legacy_selection_exists__update_arches(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
        selection_builder: BootSourceSelectionBuilder,
    ) -> None:
        builder = selection_builder.copy()
        builder.arch = "arm64"

        service.legacy_boot_source_selection_service.get_one.return_value = (
            legacy_selection
        )

        await service._ensure_legacy_selection_exists(builder)
        service.legacy_boot_source_selection_service.get_one.assert_awaited_once()
        service.legacy_boot_source_selection_service.update_by_id.assert_awaited_once_with(
            id=legacy_selection.id,
            builder=LegacyBootSourceSelectionBuilder(
                arches=legacy_selection.arches + ["arm64"],
            ),
        )
        assert builder.legacyselection_id == legacy_selection.id

    async def test_ensure_legacy_selection_exists__no_update_arch_already_present(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
        selection_builder: BootSourceSelectionBuilder,
    ) -> None:
        service.legacy_boot_source_selection_service.get_one.return_value = (
            legacy_selection
        )

        await service._ensure_legacy_selection_exists(selection_builder)
        service.legacy_boot_source_selection_service.get_one.assert_awaited_once()
        service.legacy_boot_source_selection_service.update_by_id.assert_not_awaited()
        assert selection_builder.legacyselection_id == legacy_selection.id

    async def test_ensure_legacy_selection_exists__no_update_star_selection(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
        selection_builder: BootSourceSelectionBuilder,
    ) -> None:
        legacy_star_selection = legacy_selection.copy()
        legacy_star_selection.arches = ["*"]
        service.legacy_boot_source_selection_service.get_one.return_value = (
            legacy_star_selection
        )

        await service._ensure_legacy_selection_exists(selection_builder)
        service.legacy_boot_source_selection_service.get_one.assert_awaited_once()
        service.legacy_boot_source_selection_service.update_by_id.assert_not_awaited()
        assert selection_builder.legacyselection_id == legacy_star_selection.id

    async def test_update_legacy_selection_after_deletion__delete(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
        selection: BootSourceSelection,
    ) -> None:
        service.legacy_boot_source_selection_service.get_many.return_value = [
            legacy_selection
        ]

        await service._update_legacy_selection_after_deletion([selection])

        service.legacy_boot_source_selection_service.delete_by_id.assert_awaited_once_with(
            id=legacy_selection.id
        )

    async def test_update_legacy_selection_after_deletion__update_arch(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
        selection: BootSourceSelection,
    ) -> None:
        legacy_selection_multi_arch = legacy_selection.copy()
        legacy_selection_multi_arch.arches = ["amd64", "arm64"]
        service.legacy_boot_source_selection_service.get_many.return_value = [
            legacy_selection_multi_arch
        ]

        await service._update_legacy_selection_after_deletion([selection])

        service.legacy_boot_source_selection_service.update_by_id.assert_awaited_once_with(
            id=legacy_selection.id,
            builder=LegacyBootSourceSelectionBuilder(
                arches=["arm64"],
            ),
        )

    async def test_update_legacy_selection_after_deletion__star_arches_no_op(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
        selection: BootSourceSelection,
    ) -> None:
        legacy_star_selection = legacy_selection.copy()
        legacy_star_selection.arches = ["*"]
        service.legacy_boot_source_selection_service.get_many.return_value = [
            legacy_star_selection
        ]
        service.repository.exists.return_value = True

        await service._update_legacy_selection_after_deletion([selection])

        service.legacy_boot_source_selection_service.delete_by_id.assert_not_awaited()

    async def test_update_legacy_selection_after_deletion__star_arches_delete(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
        selection: BootSourceSelection,
    ) -> None:
        legacy_star_selection = legacy_selection.copy()
        legacy_star_selection.arches = ["*"]
        service.legacy_boot_source_selection_service.get_many.return_value = [
            legacy_star_selection
        ]
        service.repository.exists.return_value = False

        await service._update_legacy_selection_after_deletion([selection])

        service.legacy_boot_source_selection_service.delete_by_id.assert_awaited_once_with(
            id=legacy_star_selection.id
        )

    async def test_ensure_selections_from_legacy__one_arch(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
    ) -> None:
        service._ensure_legacy_selection_exists = AsyncMock()
        service.legacy_boot_source_selection_service.get_many.return_value = [
            legacy_selection
        ]
        service.repository.exists.return_value = False

        await service.ensure_selections_from_legacy()

        service.repository.create.assert_awaited_once_with(
            builder=BootSourceSelectionBuilder(
                os=legacy_selection.os,
                release=legacy_selection.release,
                arch=legacy_selection.arches[0],
                boot_source_id=legacy_selection.boot_source_id,
                legacyselection_id=legacy_selection.id,
            )
        )

    async def test_ensure_selections_from_legacy__multiple_arches(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
    ) -> None:
        service._ensure_legacy_selection_exists = AsyncMock()
        legacy_selection_multi_arch = legacy_selection.copy()
        arches = ["amd64", "arm64", "ppc64el"]
        legacy_selection_multi_arch.arches = arches
        service.legacy_boot_source_selection_service.get_many.return_value = [
            legacy_selection_multi_arch
        ]
        service.repository.exists.return_value = False

        await service.ensure_selections_from_legacy()

        for arch in arches:
            service.repository.create.assert_any_await(
                builder=BootSourceSelectionBuilder(
                    os=legacy_selection.os,
                    release=legacy_selection.release,
                    arch=arch,
                    boot_source_id=legacy_selection.boot_source_id,
                    legacyselection_id=legacy_selection.id,
                )
            )

    async def test_ensure_selections_from_legacy__already_exists(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
    ) -> None:
        service.legacy_boot_source_selection_service.get_many.return_value = [
            legacy_selection
        ]
        service.repository.exists.return_value = True

        await service.ensure_selections_from_legacy()

        service.repository.create.assert_not_awaited()

    async def test_ensure_selections_from_legacy__star_selection(
        self,
        service: BootSourceSelectionsService,
        legacy_selection: LegacyBootSourceSelection,
    ) -> None:
        service._ensure_legacy_selection_exists = AsyncMock()
        legacy_star_selection = legacy_selection.copy()
        legacy_star_selection.arches = ["*"]
        service.legacy_boot_source_selection_service.get_many.return_value = [
            legacy_star_selection
        ]
        arches = ["amd64", "arm64", "armhf", "i386", "ppc64el", "s390x"]
        service.boot_source_cache_service.get_supported_arches.return_value = (
            arches
        )

        service.repository.exists.return_value = False

        await service.ensure_selections_from_legacy()

        for arch in arches:
            service.repository.create.assert_any_await(
                builder=BootSourceSelectionBuilder(
                    os=legacy_selection.os,
                    release=legacy_selection.release,
                    arch=arch,
                    boot_source_id=legacy_selection.boot_source_id,
                    legacyselection_id=legacy_selection.id,
                )
            )


class TestBootSourceSelectionStatusService(ReadOnlyServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootSourceSelectionStatusService:
        return BootSourceSelectionStatusService(
            context=Context(),
            repository=Mock(BootSourceSelectionStatusRepository),
        )

    @pytest.fixture
    def test_instance(self) -> BootSourceSelectionStatus:
        return BootSourceSelectionStatus(
            id=1,
            status=ImageStatus.DOWNLOADING,
            update_status=ImageUpdateStatus.NO_UPDATES_AVAILABLE,
            sync_percentage=50.0,
        )
