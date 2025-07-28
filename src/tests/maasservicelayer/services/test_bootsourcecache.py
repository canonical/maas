# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.builders.bootsourcecache import BootSourceCacheBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheRepository,
)
from maasservicelayer.models.bootsourcecache import BootSourceCache
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_BOOT_SOURCE_CACHE = BootSourceCache(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    os="ubuntu",
    release="noble",
    arch="amd64",
    subarch="generic",
    label="stable",
    boot_source_id=1,
    extra={},
)


class TestCommonBootSourceCacheService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootSourceCacheService:
        return BootSourceCacheService(
            context=Context(), repository=Mock(BootSourceCacheRepository)
        )

    @pytest.fixture
    def test_instance(self) -> BootSourceCache:
        return TEST_BOOT_SOURCE_CACHE


class TestBootSourceCacheService:
    @pytest.fixture
    def mock_repository(self) -> Mock:
        return Mock(BootSourceCacheRepository)

    @pytest.fixture
    def service(self, mock_repository: Mock) -> BootSourceCacheService:
        return BootSourceCacheService(
            context=Context(), repository=mock_repository
        )

    async def test_create_or_update__create(
        self, mock_repository: Mock, service: BootSourceCacheService
    ) -> None:
        mock_repository.get_one.return_value = None

        builder = BootSourceCacheBuilder(
            os="ubuntu",
            arch="amd64",
            subarch="ga-16.04",
            release="noble",
            label="stable",
            release_codename="Noble Numbat",
            release_title="24.04 LTS",
            kflavor="generic",
            boot_source_id=1,
        )

        await service.create_or_update(builder)

        mock_repository.update_by_id.assert_not_awaited()
        mock_repository.create.assert_awaited_once_with(builder=builder)

    async def test_create_or_update__update(
        self, mock_repository: Mock, service: BootSourceCacheService
    ) -> None:
        mock_repository.get_one.return_value = TEST_BOOT_SOURCE_CACHE

        builder = BootSourceCacheBuilder(
            os="ubuntu",
            arch="amd64",
            subarch="ga-16.04",
            release="noble",
            label="stable",
            release_codename="Noble Numbat",
            release_title="24.04 LTS",
            kflavor="generic",
            boot_source_id=1,
        )

        await service.create_or_update(builder)

        mock_repository.update_by_id.assert_awaited_once_with(
            id=TEST_BOOT_SOURCE_CACHE.id, builder=builder
        )
        mock_repository.create.assert_not_awaited()
