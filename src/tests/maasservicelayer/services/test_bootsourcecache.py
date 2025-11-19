# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maasservicelayer.builders.bootsourcecache import BootSourceCacheBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheClauseFactory,
    BootSourceCacheRepository,
)
from maasservicelayer.models.bootsourcecache import BootSourceCache
from maasservicelayer.models.image_manifests import ImageManifest
from maasservicelayer.services.bootsourcecache import BootSourceCacheService
from maasservicelayer.simplestreams.models import (
    BootloaderProduct,
    Datatype,
    SimpleStreamsBootloaderProductList,
)
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

    async def test_update_from_image_manifest(
        self, service: BootSourceCacheService
    ) -> None:
        service.create_or_update = AsyncMock(
            return_value=BootSourceCache(
                id=1,
                os="grub-efi-signed",
                arch="amd64",
                subarch="generic",
                release="grub-efi-signed",
                label="stable",
                bootloader_type="uefi",
                boot_source_id=1,
                extra={},
            )
        )
        service.delete_many = AsyncMock()

        manifest = [
            SimpleStreamsBootloaderProductList(
                content_id="com.ubuntu.maas:stable:1:bootloader-download",
                datatype=Datatype.image_ids,
                format="products:1.0",
                updated=utcnow(),
                products=[
                    BootloaderProduct(
                        **{
                            "product_name": "com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64",
                            "arch": "amd64",
                            "arches": "amd64",
                            "bootloader-type": "uefi",
                            "label": "stable",
                            "os": "grub-efi-signed",
                            "versions": [],
                        }
                    )
                ],
            )
        ]
        image_manifest = ImageManifest(
            boot_source_id=1,
            manifest=manifest,
            last_update=utcnow(),
        )

        await service.update_from_image_manifest(image_manifest)
        service.create_or_update.assert_awaited_once()
        service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootSourceCacheClauseFactory.and_clauses(
                    [
                        BootSourceCacheClauseFactory.with_boot_source_id(1),
                        BootSourceCacheClauseFactory.not_clause(
                            BootSourceCacheClauseFactory.with_ids({1})
                        ),
                    ]
                )
            )
        )
