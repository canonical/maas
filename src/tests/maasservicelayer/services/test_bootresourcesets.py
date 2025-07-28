# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the set LICENSE).

from datetime import datetime
from unittest.mock import Mock

import pytest

from maascommon.enums.boot_resources import BootResourceFileType
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefiles import (
    BootResourceFileClauseFactory,
)
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetClauseFactory,
    BootResourceSetsRepository,
)
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.simplestreams.models import (
    BootloaderProduct,
    BootloaderVersion,
)
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_BOOT_RESOURCE_SET = BootResourceSet(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    version="20250618",
    label="stable",
    resource_id=1,
)
TEST_BOOT_RESOURCE_SET_OLD = BootResourceSet(
    id=1,
    created=datetime(year=1999, month=1, day=1),
    updated=datetime(year=1999, month=1, day=1),
    version="20250618",
    label="stable",
    resource_id=1,
)

TEST_BOOT_RESOURCE_FILE = BootResourceFile(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    filename="filename",
    filetype=BootResourceFileType.ROOT_TGZ,
    sha256="abcdef0123456789" * 4,
    filename_on_disk="abcdef0",
    size=100,
    extra={},
    resource_set_id=1,
)


@pytest.mark.asyncio
class TestCommonBootResourceSetsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootResourceSetsService:
        return BootResourceSetsService(
            context=Context(),
            repository=Mock(BootResourceSetsRepository),
            boot_resource_files_service=Mock(BootResourceFilesService),
        )

    @pytest.fixture
    def test_instance(self) -> BootResourceSet:
        return TEST_BOOT_RESOURCE_SET


@pytest.mark.asyncio
class TestBootResourceSetsService:
    @pytest.fixture
    def mock_repository(self) -> Mock:
        return Mock(BootResourceSetsRepository)

    @pytest.fixture
    def mock_boot_resource_files_service(self) -> Mock:
        return Mock(BootResourceFilesService)

    @pytest.fixture
    def service(
        self, mock_repository: Mock, mock_boot_resource_files_service: Mock
    ) -> BootResourceSetsService:
        return BootResourceSetsService(
            context=Context(),
            repository=mock_repository,
            boot_resource_files_service=mock_boot_resource_files_service,
        )

    async def test_pre_delete_hook_deletes_files(
        self,
        mock_repository: Mock,
        mock_boot_resource_files_service: Mock,
        service: BootResourceSetsService,
    ) -> None:
        mock_repository.get_by_id.return_value = TEST_BOOT_RESOURCE_SET

        await service.delete_by_id(TEST_BOOT_RESOURCE_SET.id)

        mock_boot_resource_files_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_resource_set_id(
                    TEST_BOOT_RESOURCE_SET.id
                )
            )
        )

    async def test_pre_delete_many_hook_deletes_files(
        self,
        mock_repository: Mock,
        mock_boot_resource_files_service: Mock,
        service: BootResourceSetsService,
    ) -> None:
        mock_repository.get_many.return_value = [TEST_BOOT_RESOURCE_SET]

        await service.delete_many(query=QuerySpec())

        mock_boot_resource_files_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_resource_set_ids(
                    [TEST_BOOT_RESOURCE_SET.id]
                )
            )
        )

    async def test_get_latest_for_boot_resource(
        self,
        mock_repository: Mock,
        service: BootResourceSetsService,
    ) -> None:
        await service.get_latest_for_boot_resource(1)

        mock_repository.get_latest_for_boot_resource.assert_awaited_once_with(
            1
        )

    async def test_get_or_create_from_simplestreams_product__create(
        self,
        mock_repository: Mock,
        service: BootResourceSetsService,
    ) -> None:
        mock_repository.get_one.return_value = None
        mock_repository.create.return_value = TEST_BOOT_RESOURCE_SET

        # we have to do it this way because of fields with hyphens
        product = BootloaderProduct(
            **{
                "product_name": "com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64",
                "arch": "amd64",
                "arches": "amd64",
                "bootloader-type": "uefi",
                "label": "stable",
                "os": "grub-efi-signed",
                "versions": [BootloaderVersion(version_name="foo")],
            }
        )
        await service.get_or_create_from_simplestreams_product(product, 1)

        mock_repository.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.and_clauses(
                    [
                        BootResourceSetClauseFactory.with_resource_id(1),
                        BootResourceSetClauseFactory.with_version("foo"),
                        BootResourceSetClauseFactory.with_label("stable"),
                    ]
                )
            ),
        )
        mock_repository.create.assert_awaited_once()

    async def test_get_or_create_from_simplestreams_product__get(
        self,
        mock_repository: Mock,
        service: BootResourceSetsService,
    ) -> None:
        mock_repository.get_one.return_value = TEST_BOOT_RESOURCE_SET

        # we have to do it this way because of fields with hyphens
        product = BootloaderProduct(
            **{
                "product_name": "com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64",
                "arch": "amd64",
                "arches": "amd64",
                "bootloader-type": "uefi",
                "label": "stable",
                "os": "grub-efi-signed",
                "versions": [BootloaderVersion(version_name="foo")],
            }
        )
        await service.get_or_create_from_simplestreams_product(product, 1)

        mock_repository.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.and_clauses(
                    [
                        BootResourceSetClauseFactory.with_resource_id(1),
                        BootResourceSetClauseFactory.with_version("foo"),
                        BootResourceSetClauseFactory.with_label("stable"),
                    ]
                )
            ),
        )
        mock_repository.create.assert_not_awaited()
