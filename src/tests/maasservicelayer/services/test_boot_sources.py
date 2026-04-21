# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.constants import (
    CANDIDATE_IMAGES_STREAM_URL,
    STABLE_IMAGES_STREAM_URL,
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
from maasservicelayer.exceptions.catalog import BadRequestException
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.services.boot_sources import BootSourcesService
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.services.bootsourceselections import (
    BootSourceSelectionsService,
)
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.image_manifests import ImageManifestsService
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

    @pytest.mark.parametrize(
        "url",
        [STABLE_IMAGES_STREAM_URL, CANDIDATE_IMAGES_STREAM_URL],
    )
    async def test_pre_delete_hook_rejects_default_boot_source(
        self, service_instance, url
    ):
        now = utcnow()
        boot_source = BootSource(
            id=1,
            created=now,
            updated=now,
            name="default",
            url=url,
            keyring_filename="",
            keyring_data=b"",
            priority=1,
            skip_keyring_verification=False,
            enabled=True,
        )
        with pytest.raises(BadRequestException):
            await service_instance.pre_delete_hook(boot_source)

    async def test_pre_delete_hook_allows_non_default_boot_source(
        self, service_instance, test_instance
    ):
        await service_instance.pre_delete_hook(test_instance)

    @pytest.fixture
    def default_boot_source(self) -> BootSource:
        now = utcnow()
        return BootSource(
            id=1,
            created=now,
            updated=now,
            name="default",
            url=STABLE_IMAGES_STREAM_URL,
            keyring_filename="",
            keyring_data=b"",
            priority=1,
            skip_keyring_verification=False,
            enabled=True,
        )

    @pytest.mark.parametrize(
        "builder",
        [
            BootSourceBuilder(priority=5),
            BootSourceBuilder(enabled=False),
            BootSourceBuilder(priority=5, enabled=False),
        ],
    )
    async def test_pre_update_instance_allows_priority_and_enabled(
        self, service_instance, default_boot_source, builder
    ):
        await service_instance.pre_update_instance(
            default_boot_source, builder
        )

    @pytest.mark.parametrize(
        "builder",
        [
            BootSourceBuilder(name="new-name"),
            BootSourceBuilder(url="http://other.example.com"),
            BootSourceBuilder(keyring_filename="/new/path"),
            BootSourceBuilder(keyring_data=b"new-data"),
            BootSourceBuilder(skip_keyring_verification=True),
        ],
    )
    async def test_pre_update_instance_rejects_disallowed_fields(
        self, service_instance, default_boot_source, builder
    ):
        with pytest.raises(BadRequestException):
            await service_instance.pre_update_instance(
                default_boot_source, builder
            )

    async def test_pre_update_instance_allows_unchanged_disallowed_fields(
        self, service_instance, default_boot_source
    ):
        builder = BootSourceBuilder(
            name=default_boot_source.name,
            keyring_filename=default_boot_source.keyring_filename,
            keyring_data=default_boot_source.keyring_data,
            skip_keyring_verification=default_boot_source.skip_keyring_verification,
            priority=5,
        )
        await service_instance.pre_update_instance(
            default_boot_source, builder
        )

    @pytest.mark.parametrize(
        "builder",
        [
            BootSourceBuilder(name="new-name"),
            BootSourceBuilder(url="http://other.example.com"),
            BootSourceBuilder(keyring_filename="/new/path"),
            BootSourceBuilder(keyring_data=b"new-data"),
            BootSourceBuilder(skip_keyring_verification=True),
            BootSourceBuilder(priority=5),
            BootSourceBuilder(enabled=False),
        ],
    )
    async def test_pre_update_instance_allows_any_field_for_non_default(
        self, service_instance, test_instance, builder
    ):
        await service_instance.pre_update_instance(test_instance, builder)
