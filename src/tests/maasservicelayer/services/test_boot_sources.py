# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.events import EventTypeEnum
from maascommon.workflows.bootresource import (
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
)
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
from maasservicelayer.services.boot_sources import BootSourcesService
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
)
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.image_manifests import ImageManifestsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestBootSourcesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootSourcesService:
        return BootSourcesService(
            context=Context(),
            repository=Mock(BootSourcesRepository),
            boot_source_cache_service=Mock(BootSourceCacheService),
            boot_source_selections_service=Mock(BootSourceSelectionsService),
            image_manifests_service=Mock(ImageManifestsService),
            events_service=Mock(EventsService),
            temporal_service=Mock(TemporalService),
        )

    @pytest.fixture
    def test_instance(self) -> BootSource:
        now = utcnow()
        return BootSource(
            id=1,
            created=now,
            updated=now,
            name="Test Boot Source",
            url="http://example.com",
            keyring_filename="/path/to/keyring_file.gpg",
            keyring_data=b"",
            priority=10,
            skip_keyring_verification=False,
            enabled=True,
        )

    async def test_delete(self, test_instance):
        boot_source = test_instance

        repository_mock = Mock(BootSourcesRepository)
        repository_mock.get_one.return_value = boot_source
        repository_mock.delete_by_id.return_value = boot_source

        boot_source_cache_service_mock = Mock(BootSourceCacheService)
        boot_source_selections_service_mock = Mock(BootSourceSelectionsService)
        image_manifests_service = Mock(ImageManifestsService)
        events_service_mock = Mock(EventsService)

        boot_source_service = BootSourcesService(
            context=Context(),
            repository=repository_mock,
            boot_source_cache_service=boot_source_cache_service_mock,
            boot_source_selections_service=boot_source_selections_service_mock,
            image_manifests_service=image_manifests_service,
            events_service=events_service_mock,
            temporal_service=Mock(TemporalService),
        )

        query = Mock(QuerySpec)
        await boot_source_service.delete_one(query)

        repository_mock.delete_by_id.assert_called_once_with(id=boot_source.id)

        boot_source_cache_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.with_boot_source_ids(
                    [boot_source.id]
                )
            )
        )
        boot_source_selections_service_mock.delete_many.assert_called_once_with(
            query=QuerySpec(
                where=BootSourceSelectionClauseFactory.with_boot_source_ids(
                    [boot_source.id]
                )
            )
        )
        image_manifests_service.delete_many.assert_called_once_with(
            {boot_source.id}
        )

    async def test_disable_all(self, service_instance):
        service_instance.repository.update_many.return_value = []
        await service_instance.disable_all()
        service_instance.repository.update_many.assert_called_once_with(
            query=QuerySpec(),
            builder=BootSourceBuilder(enabled=False),
        )

    async def test_post_create_hook_creates_event(
        self, service_instance, test_instance
    ):
        service_instance.repository.create.return_value = test_instance

        await service_instance.create(BootSourceBuilder())

        service_instance.events_service.record_event.assert_called_once_with(
            event_type=EventTypeEnum.BOOT_SOURCE,
            event_description=f"Created boot source {test_instance.url}",
        )

    async def test_post_create_hook_starts_fetch_manifest(
        self, service_instance, test_instance
    ):
        service_instance.repository.create.return_value = test_instance

        await service_instance.create(BootSourceBuilder())

        service_instance.temporal_service.register_workflow_call.assert_called_once_with(
            workflow_name=FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
            workflow_id=f"fetch-manifest-boot-source-{test_instance.id}",
            parameter=test_instance.id,
            wait=False,
        )
