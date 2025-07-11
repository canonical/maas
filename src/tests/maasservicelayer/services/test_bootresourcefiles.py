# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.boot_resources import BootResourceFileType
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresourcefiles import (
    BootResourceFilesRepository,
)
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
    SHORTSHA256_MIN_PREFIX_LEN,
)
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
class TestBootResourceFilesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootResourceFilesService:
        return BootResourceFilesService(
            context=Context(),
            repository=Mock(BootResourceFilesRepository),
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

    @pytest.mark.parametrize(
        "matching_resource, collisions, sha, expected_filename",
        [
            (
                TEST_BOOT_RESOURCE_FILE,
                [],
                TEST_BOOT_RESOURCE_FILE.sha256,
                TEST_BOOT_RESOURCE_FILE.filename_on_disk,
            ),  # file with the same sha exists
            (
                None,
                [],
                "a" * 64,
                "a" * SHORTSHA256_MIN_PREFIX_LEN,
            ),  # No matching resource, no collisions
            (
                None,
                [TEST_BOOT_RESOURCE_FILE],
                "abcdef0" + "0" * 47,
                "abcdef00",
            ),  # collision, use the next char
            (
                None,
                [TEST_BOOT_RESOURCE_FILE, TEST_BOOT_RESOURCE_FILE_FULL_SHA],
                TEST_BOOT_RESOURCE_FILE_FULL_SHA.sha256[:-1] + "a",
                TEST_BOOT_RESOURCE_FILE_FULL_SHA.sha256[:-1] + "a",
            ),  # the collision starts with the same 63 chars, we have to use the full sha
        ],
    )
    async def test_calculate_filename_on_disk(
        self,
        matching_resource: BootResourceFile | None,
        collisions: list[BootResourceFile],
        sha: str,
        expected_filename: str,
    ) -> None:
        repo = Mock(BootResourceFilesRepository)
        repo.get_one.return_value = matching_resource
        repo.get_many.return_value = collisions
        service = BootResourceFilesService(context=Context(), repository=repo)
        filename = await service.calculate_filename_on_disk(sha)
        assert filename == expected_filename

    async def test_get_files_in_resource_set(self) -> None:
        repo = Mock(BootResourceFilesRepository)
        service = BootResourceFilesService(context=Context(), repository=repo)
        await service.get_files_in_resource_set(1)
        repo.get_files_in_resource_set.assert_called_once_with(1)
