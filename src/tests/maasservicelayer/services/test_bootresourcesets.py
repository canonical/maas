# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the set LICENSE).
import copy
from datetime import datetime
import math
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
from maasservicelayer.services.bootresourcefilesync import (
    BootResourceFileSyncService,
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
TEST_BOOT_RESOURCE_SET_2 = BootResourceSet(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    version="20250826",
    label="stable",
    resource_id=2,
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
            boot_resource_file_sync_service=Mock(BootResourceFileSyncService),
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
    def mock_boot_resource_file_sync_service(self) -> Mock:
        return Mock(BootResourceFileSyncService)

    @pytest.fixture
    def mock_boot_resource_files_service(self) -> Mock:
        return Mock(BootResourceFilesService)

    @pytest.fixture
    def service(
        self,
        mock_repository: Mock,
        mock_boot_resource_files_service: Mock,
        mock_boot_resource_file_sync_service: Mock,
    ) -> BootResourceSetsService:
        return BootResourceSetsService(
            context=Context(),
            repository=mock_repository,
            boot_resource_files_service=mock_boot_resource_files_service,
            boot_resource_file_sync_service=mock_boot_resource_file_sync_service,
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

    async def test_create_or_update_from_simplestreams_product__create(
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
        await service.create_or_update_from_simplestreams_product(product, 1)

        mock_repository.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.and_clauses(
                    [
                        BootResourceSetClauseFactory.with_resource_id(1),
                        BootResourceSetClauseFactory.with_version("foo"),
                    ]
                )
            ),
        )
        mock_repository.create.assert_awaited_once()
        mock_repository.update_by_id.assert_not_awaited()

    async def test_create_or_update_from_simplestreams_product__update(
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
        await service.create_or_update_from_simplestreams_product(product, 1)

        mock_repository.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.and_clauses(
                    [
                        BootResourceSetClauseFactory.with_resource_id(1),
                        BootResourceSetClauseFactory.with_version("foo"),
                    ]
                )
            ),
        )
        mock_repository.create.assert_not_awaited()
        mock_repository.update_by_id.assert_awaited_once()

    @pytest.mark.parametrize(
        "synced_size, expected_progress, expected_complete",
        [
            (0, 0.0, False),
            (300, 100.0, True),
            (100, 33.333333333, False),
            (270, 90.00, False),
        ],
    )
    async def test_get_sync_progress(
        self,
        synced_size: int,
        expected_progress: float,
        expected_complete: bool,
        mock_repository: Mock,
        mock_boot_resource_files_service: Mock,
        mock_boot_resource_file_sync_service: Mock,
        service: BootResourceSetsService,
    ) -> None:
        mock_repository.get_by_id.return_value = Mock(BootResourceSet)
        mock_boot_resource_file_sync_service.get_regions_count.return_value = 1
        mock_boot_resource_files_service.get_files_in_resource_set.return_value = [
            BootResourceFile(
                id=i,
                created=utcnow(),
                updated=utcnow(),
                filename="test",
                filetype=BootResourceFileType.SQUASHFS_IMAGE,
                extra={},
                sha256="a" * 64,
                size=100,
                filename_on_disk="a" * 7,
            )
            for i in range(3)
        ]
        mock_boot_resource_file_sync_service.get_current_sync_size_for_files.return_value = synced_size
        sync_progress = await service.get_sync_progress(1)
        assert math.isclose(sync_progress, expected_progress)
        sync_complete = await service.is_sync_complete(1)
        assert sync_complete is expected_complete

        mock_repository.get_by_id.assert_called_with(id=1)
        mock_boot_resource_files_service.get_files_in_resource_set.assert_called_with(
            1
        )
        mock_boot_resource_file_sync_service.get_current_sync_size_for_files.assert_called_with(
            {0, 1, 2}
        )

    async def test_get_latest_complete_set_for_boot_resource(
        self,
        service: BootResourceSetsService,
        mock_repository: Mock,
        mock_boot_resource_files_service: Mock,
        mock_boot_resource_file_sync_service: Mock,
    ) -> None:
        boot_resource_id = 42

        mock_repository.get_many_newest_to_oldest_for_boot_resource.return_value = [
            TEST_BOOT_RESOURCE_SET_2,
            TEST_BOOT_RESOURCE_SET,
        ]

        mock_boot_resource_file_sync_service.get_regions_count.return_value = 1

        mock_boot_resource_files_service.get_files_in_resource_set.return_value = [
            TEST_BOOT_RESOURCE_FILE
        ]

        mock_boot_resource_file_sync_service.get_current_sync_size_for_files.return_value = TEST_BOOT_RESOURCE_FILE.size

        latest_complete_set = (
            await service.get_latest_complete_set_for_boot_resource(
                boot_resource_id
            )
        )

        assert latest_complete_set == TEST_BOOT_RESOURCE_SET_2

    async def test_get_latest_complete_set_for_boot_resource_no_sets(
        self,
        service: BootResourceSetsService,
        mock_repository: Mock,
        mock_boot_resource_file_sync_service: Mock,
    ) -> None:
        boot_resource_id = 42

        mock_repository.get_many_newest_to_oldest_for_boot_resource.return_value = []

        mock_boot_resource_file_sync_service.get_regions_count.return_value = 1

        latest_complete_set = (
            await service.get_latest_complete_set_for_boot_resource(
                boot_resource_id
            )
        )

        assert latest_complete_set is None

    async def test_get_latest_complete_set_for_boot_resource_only_set_isnt_synced(
        self,
        service: BootResourceSetsService,
        mock_repository: Mock,
        mock_boot_resource_files_service: Mock,
        mock_boot_resource_file_sync_service: Mock,
    ) -> None:
        boot_resource_id = 42

        mock_repository.get_many_newest_to_oldest_for_boot_resource.return_value = [
            TEST_BOOT_RESOURCE_SET
        ]

        mock_boot_resource_file_sync_service.get_regions_count.return_value = 2

        mock_boot_resource_files_service.get_files_in_resource_set.return_value = [
            TEST_BOOT_RESOURCE_FILE
        ]

        # Not fully synced on one region
        mock_boot_resource_file_sync_service.get_current_sync_size_for_files.return_value = (
            TEST_BOOT_RESOURCE_FILE.size * 1.5
        )

        latest_complete_set = (
            await service.get_latest_complete_set_for_boot_resource(
                boot_resource_id
            )
        )

        assert latest_complete_set is None

    async def test_is_usable(
        self,
        service: BootResourceSetsService,
        mock_boot_resource_files_service: Mock,
    ) -> None:
        mock_boot_resource_files_service.get_files_in_resource_set.return_value = [
            BootResourceFile(
                id=1,
                created=utcnow(),
                updated=utcnow(),
                filename="filename1",
                filetype=BootResourceFileType.BOOT_KERNEL,
                sha256="abcdef0123456789" * 4,
                filename_on_disk="abcdef01",
                size=100,
                extra={},
                resource_set_id=1,
            ),
            BootResourceFile(
                id=2,
                created=utcnow(),
                updated=utcnow(),
                filename="filename2",
                filetype=BootResourceFileType.BOOT_INITRD,
                sha256="a1f54f3d1f1537bb" * 4,
                filename_on_disk="abcdef02",
                size=1001,
                extra={},
                resource_set_id=1,
            ),
            BootResourceFile(
                id=3,
                created=utcnow(),
                updated=utcnow(),
                filename="filename3",
                filetype=BootResourceFileType.SQUASHFS_IMAGE,
                sha256="14564738172a6284" * 4,
                filename_on_disk="abcdef03",
                size=256,
                extra={},
                resource_set_id=1,
            ),
        ]

        resource_set = BootResourceSet(
            id=1,
            version="20250826",
            label="stable",
            resource_id=1,
        )

        is_usable = await service.is_usable(resource_set.id)

        assert is_usable

    async def test_is_not_usable(
        self,
        service: BootResourceSetsService,
        mock_boot_resource_files_service: Mock,
    ) -> None:
        file = copy.deepcopy(TEST_BOOT_RESOURCE_FILE)
        file.filetype = BootResourceFileType.BOOT_DTB
        mock_boot_resource_files_service.get_files_in_resource_set.return_value = [
            file
        ]

        resource_set = BootResourceSet(
            id=1,
            version="20250826",
            label="stable",
            resource_id=1,
        )

        is_usable = await service.is_usable(resource_set.id)

        assert not is_usable

    async def test_is_xinstallable(
        self,
        service: BootResourceSetsService,
        mock_boot_resource_files_service: Mock,
    ) -> None:
        mock_boot_resource_files_service.get_files_in_resource_set.return_value = [
            TEST_BOOT_RESOURCE_FILE
        ]

        resource_set = BootResourceSet(
            id=1,
            version="20250826",
            label="stable",
            resource_id=1,
        )

        is_xinstallable = await service.is_xinstallable(resource_set.id)

        assert is_xinstallable

    async def test_is_not_xinstallable(
        self,
        service: BootResourceSetsService,
        mock_boot_resource_files_service: Mock,
    ) -> None:
        file = copy.deepcopy(TEST_BOOT_RESOURCE_FILE)
        file.filetype = BootResourceFileType.BOOT_KERNEL
        mock_boot_resource_files_service.get_files_in_resource_set.return_value = [
            file
        ]

        resource_set = BootResourceSet(
            id=1,
            version="20250826",
            label="stable",
            resource_id=1,
        )

        is_xinstallable = await service.is_xinstallable(resource_set.id)

        assert not is_xinstallable
