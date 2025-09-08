# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionsRepository,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
)
from maasservicelayer.services.events import EventsService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestBootSourceSelectionsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootSourceSelectionsService:
        return BootSourceSelectionsService(
            context=Context(),
            repository=Mock(BootSourceSelectionsRepository),
            boot_source_cache_service=Mock(BootSourceCacheService),
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
            arches=["amd64"],
            subarches=["*"],
            labels=["*"],
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
            arches=["amd64"],
            subarches=["*"],
            labels=["*"],
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
        with pytest.raises(NotFoundException):
            await self.test_create(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id(
        self, service_instance, test_instance, builder_model
    ):
        service_instance.repository.get_by_id.return_value = test_instance
        service_instance.repository.update_by_id.return_value = test_instance
        builder = BootSourceSelectionBuilder(
            os="ubuntu",
            release="jammy",
            arches=["amd64"],
            subarches=["*"],
            labels=["*"],
            boot_source_id=1,
        )
        objs = await service_instance.update_by_id(test_instance.id, builder)
        assert objs == test_instance
        service_instance.repository.update_by_id.assert_awaited_once_with(
            id=test_instance.id, builder=builder
        )

    async def test_update_by_id_with_available_boot_resource(
        self, service_instance, test_instance, builder_model
    ):
        service_instance.boot_source_cache_service.exists.return_value = True
        await self.test_update_by_id(
            service_instance, test_instance, builder_model
        )

    async def test_update_by_id_with_inexistent_boot_resource(
        self, service_instance, test_instance, builder_model
    ):
        service_instance.boot_source_cache_service.exists.return_value = False
        with pytest.raises(NotFoundException):
            await self.test_update_by_id(
                service_instance, test_instance, builder_model
            )

    async def test_update_by_id_not_found(
        self, service_instance, builder_model
    ):
        builder = Mock(
            return_value=BootSourceSelectionBuilder(
                os="ubuntu",
                release="jammy",
                arches=["amd64"],
                subarches=["*"],
                labels=["*"],
                boot_source_id=1,
            )
        )
        await super().test_update_by_id_not_found(service_instance, builder)

    async def test_update_by_id_etag_not_matching(
        self, service_instance, test_instance, builder_model
    ):
        builder = Mock(
            return_value=BootSourceSelectionBuilder(
                os="ubuntu",
                release="jammy",
                arches=["amd64"],
                subarches=["*"],
                labels=["*"],
                boot_source_id=1,
            )
        )
        await super().test_update_by_id_etag_not_matching(
            service_instance, test_instance, builder
        )

    async def test_update_by_id_etag_match(
        self, service_instance, test_instance, builder_model
    ):
        builder = Mock(
            return_value=BootSourceSelectionBuilder(
                os="ubuntu",
                release="jammy",
                arches=["amd64"],
                subarches=["*"],
                labels=["*"],
                boot_source_id=1,
            )
        )
        await super().test_update_by_id_etag_match(
            service_instance, test_instance, builder
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
