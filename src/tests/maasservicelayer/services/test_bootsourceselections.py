# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.boot_resources import ImageStatus, ImageUpdateStatus
from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
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
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
    BootSourceSelectionStatusService,
)
from maasservicelayer.services.events import EventsService
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
        )

    @pytest.fixture
    def builder_model(self) -> type[BootSourceSelectionBuilder]:
        return BootSourceSelectionBuilder

    async def test_create(
        self, service_instance, test_instance, builder_model
    ):
        service_instance.repository.create.return_value = test_instance
        builder = BootSourceSelectionBuilder(
            os="ubuntu",
            release="jammy",
            arch="amd64",
            boot_source_id=1,
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
        await self.test_create(service_instance, test_instance, builder_model)

    async def test_create_with_inexistent_boot_resource(
        self, service_instance, test_instance, builder_model
    ):
        service_instance.boot_source_cache_service.exists.return_value = False
        with pytest.raises(BadRequestException):
            await self.test_create(
                service_instance, test_instance, builder_model
            )

    async def test_create_without_boot_source_cache(
        self, service_instance, builder_model
    ) -> None:
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
            events_service=Mock(EventsService),
        )

    async def test_get_all_highest_priority(
        self, service: BootSourceSelectionsService
    ) -> None:
        await service.get_all_highest_priority()
        service.repository.get_all_highest_priority.assert_awaited_once()


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
