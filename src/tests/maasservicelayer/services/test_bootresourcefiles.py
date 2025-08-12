# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import math
from unittest.mock import call, Mock

import pytest

from maascommon.enums.boot_resources import BootResourceFileType
from maascommon.workflows.bootresource import (
    DELETE_BOOTRESOURCE_WORKFLOW_NAME,
    merge_resource_delete_param,
    ResourceDeleteParam,
    ResourceIdentifier,
)
from maasservicelayer.builders.bootresourcefiles import BootResourceFileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefiles import (
    BootResourceFileClauseFactory,
    BootResourceFilesRepository,
)
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
    SHORTSHA256_MIN_PREFIX_LEN,
)
from maasservicelayer.services.bootresourcefilesync import (
    BootResourceFileSyncService,
)
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.simplestreams.models import ImageFile
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

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

TEST_BOOT_RESOURCE_FILE_FULL_SHA = BootResourceFile(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    filename="filename",
    filetype=BootResourceFileType.ROOT_TGZ,
    sha256="abcdef0123456789" * 4,
    filename_on_disk="abcdef0123456789" * 4,
    size=100,
    extra={},
    resource_set_id=1,
)


@pytest.mark.asyncio
class TestCommonBootResourceFilesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootResourceFilesService:
        return BootResourceFilesService(
            context=Context(),
            repository=Mock(BootResourceFilesRepository),
            boot_resource_file_sync_service=Mock(BootResourceFileSyncService),
            temporal_service=Mock(TemporalService),
        )

    @pytest.fixture
    def test_instance(self) -> BootResourceFile:
        now = utcnow()
        return BootResourceFile(
            id=1,
            created=now,
            updated=now,
            filename="filename",
            filetype=BootResourceFileType.ROOT_TGZ,
            sha256="abcdef",
            filename_on_disk="abcdef",
            size=100,
            extra={},
            resource_set_id=1,
        )


class TestBootResourceFilesService:
    @pytest.fixture
    def mock_repository(self) -> Mock:
        return Mock(BootResourceFilesRepository)

    @pytest.fixture
    def mock_boot_resource_file_sync_service(self) -> Mock:
        return Mock(BootResourceFileSyncService)

    @pytest.fixture
    def mock_temporal_service(self) -> Mock:
        return Mock(TemporalService)

    @pytest.fixture
    def service(
        self,
        mock_repository: Mock,
        mock_boot_resource_file_sync_service: Mock,
        mock_temporal_service: Mock,
    ) -> BootResourceFilesService:
        return BootResourceFilesService(
            context=Context(),
            repository=mock_repository,
            boot_resource_file_sync_service=mock_boot_resource_file_sync_service,
            temporal_service=mock_temporal_service,
        )

    @pytest.mark.parametrize(
        "matching_resources, collisions, sha, expected_filename",
        [
            (
                [TEST_BOOT_RESOURCE_FILE],
                [],
                TEST_BOOT_RESOURCE_FILE.sha256,
                TEST_BOOT_RESOURCE_FILE.filename_on_disk,
            ),  # file with the same sha exists
            (
                [],
                [],
                "a" * 64,
                "a" * SHORTSHA256_MIN_PREFIX_LEN,
            ),  # No matching resources, no collisions
            (
                [],
                [TEST_BOOT_RESOURCE_FILE],
                "abcdef0" + "0" * 47,
                "abcdef00",
            ),  # collision, use the next char
            (
                [],
                [TEST_BOOT_RESOURCE_FILE, TEST_BOOT_RESOURCE_FILE_FULL_SHA],
                TEST_BOOT_RESOURCE_FILE_FULL_SHA.sha256[:-1] + "a",
                TEST_BOOT_RESOURCE_FILE_FULL_SHA.sha256[:-1] + "a",
            ),  # the collision starts with the same 63 chars, we have to use the full sha
        ],
    )
    async def test_calculate_filename_on_disk(
        self,
        matching_resources: list[BootResourceFile],
        collisions: list[BootResourceFile],
        sha: str,
        expected_filename: str,
        mock_repository: Mock,
        service: BootResourceFilesService,
    ) -> None:
        mock_repository.get_many.side_effect = [matching_resources, collisions]
        filename = await service.calculate_filename_on_disk(sha)
        assert filename == expected_filename

    async def test_get_files_in_resource_set(
        self,
        mock_repository: Mock,
        service: BootResourceFilesService,
    ) -> None:
        await service.get_files_in_resource_set(1)
        mock_repository.get_files_in_resource_set.assert_called_once_with(1)

    async def test_post_delete_hook_last_file(
        self,
        mock_repository: Mock,
        mock_temporal_service: Mock,
        service: BootResourceFilesService,
    ) -> None:
        mock_repository.get_by_id.return_value = TEST_BOOT_RESOURCE_FILE
        mock_repository.delete_by_id.return_value = TEST_BOOT_RESOURCE_FILE
        mock_repository.exists.return_value = False

        await service.delete_by_id(TEST_BOOT_RESOURCE_FILE.id)
        mock_temporal_service.register_or_update_workflow_call.assert_called_once_with(
            DELETE_BOOTRESOURCE_WORKFLOW_NAME,
            parameter=ResourceDeleteParam(
                files=[
                    ResourceIdentifier(
                        sha256=TEST_BOOT_RESOURCE_FILE.sha256,
                        filename_on_disk=TEST_BOOT_RESOURCE_FILE.filename_on_disk,
                    )
                ]
            ),
            parameter_merge_func=merge_resource_delete_param,
        )

    async def test_post_delete_hook_another_file_exists(
        self,
        mock_repository: Mock,
        mock_temporal_service: Mock,
        service: BootResourceFilesService,
    ) -> None:
        mock_repository.get_by_id.return_value = TEST_BOOT_RESOURCE_FILE
        mock_repository.delete_by_id.return_value = TEST_BOOT_RESOURCE_FILE
        mock_repository.exists.return_value = True

        await service.delete_by_id(TEST_BOOT_RESOURCE_FILE.id)
        mock_temporal_service.register_or_update_workflow_call.assert_not_called()

    async def test_post_delete_many_hook_last_file(
        self,
        mock_repository: Mock,
        mock_temporal_service: Mock,
        service: BootResourceFilesService,
    ) -> None:
        mock_repository.delete_many.return_value = [TEST_BOOT_RESOURCE_FILE]
        mock_repository.get_many.return_value = []

        await service.delete_many(query=QuerySpec())
        mock_temporal_service.register_or_update_workflow_call.assert_called_once_with(
            DELETE_BOOTRESOURCE_WORKFLOW_NAME,
            parameter=ResourceDeleteParam(
                files=[
                    ResourceIdentifier(
                        sha256=TEST_BOOT_RESOURCE_FILE.sha256,
                        filename_on_disk=TEST_BOOT_RESOURCE_FILE.filename_on_disk,
                    )
                ]
            ),
            parameter_merge_func=merge_resource_delete_param,
        )

    async def test_post_delete_many_hook_another_file_exists(
        self,
        mock_repository: Mock,
        mock_temporal_service: Mock,
        service: BootResourceFilesService,
    ) -> None:
        mock_repository.delete_many.return_value = [TEST_BOOT_RESOURCE_FILE]
        mock_repository.get_many.return_value = [
            TEST_BOOT_RESOURCE_FILE_FULL_SHA
        ]

        await service.delete_many(query=QuerySpec())
        mock_temporal_service.register_or_update_workflow_call.assert_not_called()

    async def test_get_or_create_from_simplestreams_file__get(
        self,
        mock_repository: Mock,
        service: BootResourceFilesService,
    ) -> None:
        mock_repository.get_one.return_value = TEST_BOOT_RESOURCE_FILE
        # for calculate_filename_on_disk
        mock_repository.get_many.return_value = [TEST_BOOT_RESOURCE_FILE]

        file = ImageFile(
            ftype="boot-initrd",
            kpackage="linux-generic",
            path="oracular/amd64/20250404/ga-24.10/generic/boot-initrd",
            sha256=TEST_BOOT_RESOURCE_FILE.sha256,
            size=75990212,
        )

        await service.get_or_create_from_simplestreams_file(file, 1)

        mock_repository.get_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.with_sha256(file.sha256)
            )
        )
        mock_repository.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.and_clauses(
                    [
                        BootResourceFileClauseFactory.with_resource_set_id(1),
                        BootResourceFileClauseFactory.with_filename(
                            "boot-initrd"
                        ),
                    ]
                )
            )
        )
        mock_repository.create.assert_not_awaited()
        mock_repository.delete_by_id.assert_not_awaited()

    async def test_get_or_create_from_simplestreams_file__create(
        self,
        mock_repository: Mock,
        service: BootResourceFilesService,
    ) -> None:
        mock_repository.get_one.return_value = None
        # for calculate_filename_on_disk
        mock_repository.get_many.return_value = []

        file = ImageFile(
            ftype="boot-initrd",
            kpackage="linux-generic",
            path="oracular/amd64/20250404/ga-24.10/generic/boot-initrd",
            sha256="e42de3a72d142498c2945e8b0e1b9bad2fc031a2224b7497ccaca66199b51f93",
            size=75990212,
        )
        builder = BootResourceFileBuilder.from_simplestreams_file(file, 1)
        builder.filename_on_disk = file.sha256[:SHORTSHA256_MIN_PREFIX_LEN]

        await service.get_or_create_from_simplestreams_file(file, 1)

        mock_repository.get_many.assert_has_awaits(
            [
                call(
                    query=QuerySpec(
                        where=BootResourceFileClauseFactory.with_sha256(
                            file.sha256
                        )
                    )
                ),
                call(
                    query=QuerySpec(
                        where=BootResourceFileClauseFactory.with_sha256_starting_with(
                            file.sha256[:SHORTSHA256_MIN_PREFIX_LEN]
                        )
                    )
                ),
            ]
        )
        mock_repository.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.and_clauses(
                    [
                        BootResourceFileClauseFactory.with_resource_set_id(1),
                        BootResourceFileClauseFactory.with_filename(
                            "boot-initrd"
                        ),
                    ]
                )
            )
        )
        mock_repository.create.assert_awaited_once_with(builder=builder)
        mock_repository.delete_by_id.assert_not_awaited()

    async def test_get_or_create_from_simplestreams_file__delete_and_create(
        self,
        mock_repository: Mock,
        service: BootResourceFilesService,
    ) -> None:
        mock_repository.get_one.return_value = TEST_BOOT_RESOURCE_FILE
        # for calculate_filename_on_disk
        mock_repository.get_many.return_value = []

        file = ImageFile(
            ftype="boot-initrd",
            kpackage="linux-generic",
            path="oracular/amd64/20250404/ga-24.10/generic/boot-initrd",
            sha256="e42de3a72d142498c2945e8b0e1b9bad2fc031a2224b7497ccaca66199b51f93",
            size=75990212,
        )
        builder = BootResourceFileBuilder.from_simplestreams_file(file, 1)
        builder.filename_on_disk = file.sha256[:SHORTSHA256_MIN_PREFIX_LEN]

        await service.get_or_create_from_simplestreams_file(file, 1)

        mock_repository.get_many.assert_has_awaits(
            [
                call(
                    query=QuerySpec(
                        where=BootResourceFileClauseFactory.with_sha256(
                            file.sha256
                        )
                    )
                ),
                call(
                    query=QuerySpec(
                        where=BootResourceFileClauseFactory.with_sha256_starting_with(
                            file.sha256[:SHORTSHA256_MIN_PREFIX_LEN]
                        )
                    )
                ),
            ]
        )
        mock_repository.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceFileClauseFactory.and_clauses(
                    [
                        BootResourceFileClauseFactory.with_resource_set_id(1),
                        BootResourceFileClauseFactory.with_filename(
                            "boot-initrd"
                        ),
                    ]
                )
            )
        )
        mock_repository.delete_by_id.assert_awaited_once_with(
            id=TEST_BOOT_RESOURCE_FILE.id
        )
        mock_repository.create.assert_awaited_once_with(builder=builder)

    @pytest.mark.parametrize(
        "synced_size, expected_progress, expected_complete",
        [
            (0, 0.0, False),
            (100, 100.0, True),
            (50, 50.0, False),
        ],
    )
    async def test_get_sync_progress(
        self,
        synced_size: int,
        expected_progress: float,
        expected_complete: bool,
        mock_repository: Mock,
        mock_boot_resource_file_sync_service: Mock,
        service: BootResourceFilesService,
    ) -> None:
        mock_boot_resource_file_sync_service.get_regions_count.return_value = 1
        mock_repository.get_by_id.return_value = BootResourceFile(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            filename="test",
            filetype=BootResourceFileType.SQUASHFS_IMAGE,
            extra={},
            sha256="a" * 64,
            size=100,
            filename_on_disk="a" * 7,
        )
        mock_boot_resource_file_sync_service.get_current_sync_size_for_files.return_value = synced_size
        sync_progress = await service.get_sync_progress(1)
        assert math.isclose(sync_progress, expected_progress)
        sync_complete = await service.is_sync_complete(1)
        assert sync_complete is expected_complete

        mock_repository.get_by_id.assert_called_with(id=1)
        mock_boot_resource_file_sync_service.get_current_sync_size_for_files.assert_called_with(
            {1}
        )
