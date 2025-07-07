# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.boot_resources import BootResourceFileType
from maasservicelayer.builders.bootresourcefiles import BootResourceFileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresourcefiles import (
    BootResourceFileClauseFactory,
    BootResourceFilesRepository,
)
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from tests.fixtures.factories.bootresourcefiles import (
    create_test_bootresourcefile_entry,
)
from tests.fixtures.factories.bootresourcesets import (
    create_test_bootresourceset_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestBootResourceFileClauseFactory:
    def test_with_sha256_starting_with(self) -> None:
        clause = BootResourceFileClauseFactory.with_sha256_starting_with(
            "abcdef"
        )
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootresourcefile.sha256 LIKE 'abcdef' || '%'"
        )

    def test_with_sha256(self) -> None:
        sha = "abcdef" * 8
        clause = BootResourceFileClauseFactory.with_sha256(sha)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == f"maasserver_bootresourcefile.sha256 = '{sha}'"
        )

    def test_with_resource_set_id(self) -> None:
        clause = BootResourceFileClauseFactory.with_resource_set_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_bootresourcefile.resource_set_id = 1"
        )


class TestBootResourceFileRepository(RepositoryCommonTests[BootResourceFile]):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootResourceFile]:
        return [
            await create_test_bootresourcefile_entry(
                fixture,
                filename=f"filename-{i}",
                filetype=BootResourceFileType.SQUASHFS_IMAGE,
                sha256=f"abcdef{i}",
                filename_on_disk=f"abcdef{i}",
                size=100,
                resource_set_id=1,
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootResourceFile:
        return await create_test_bootresourcefile_entry(
            fixture,
            filename="filename",
            filetype=BootResourceFileType.SQUASHFS_IMAGE,
            sha256="abcdef",
            filename_on_disk="abcdef",
            size=100,
            resource_set_id=1,
        )

    @pytest.fixture
    async def instance_builder(
        self, *args, **kwargs
    ) -> BootResourceFileBuilder:
        return BootResourceFileBuilder(
            filename="filename",
            filetype=BootResourceFileType.SQUASHFS_IMAGE,
            sha256="abcdef",
            filename_on_disk="abcdef",
            size=100,
            extra={},
            resource_set_id=1,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[BootResourceFileBuilder]:
        return BootResourceFileBuilder

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootResourceFilesRepository:
        return BootResourceFilesRepository(Context(connection=db_connection))

    async def test_get_files_in_resource_set(
        self,
        fixture: Fixture,
        repository_instance: BootResourceFilesRepository,
    ) -> None:
        resource_set1 = await create_test_bootresourceset_entry(
            fixture, version="20250618", label="stable", resource_id=1
        )
        resource_set2 = await create_test_bootresourceset_entry(
            fixture, version="20240720", label="stable", resource_id=1
        )
        file1 = await create_test_bootresourcefile_entry(
            fixture,
            filename="file1",
            filetype=BootResourceFileType.SQUASHFS_IMAGE,
            sha256="abcdef",
            filename_on_disk="abcdef",
            size=100,
            extra={},
            resource_set_id=resource_set1.id,
        )
        file2 = await create_test_bootresourcefile_entry(
            fixture,
            filename="file2",
            filetype=BootResourceFileType.SQUASHFS_IMAGE,
            sha256="0123456",
            filename_on_disk="0123456",
            size=100,
            extra={},
            resource_set_id=resource_set2.id,
        )
        file_in_set1 = await repository_instance.get_files_in_resource_set(
            resource_set1.id
        )
        assert file_in_set1 == [file1]

        file_in_set2 = await repository_instance.get_files_in_resource_set(
            resource_set2.id
        )
        assert file_in_set2 == [file2]

        empty_list = await repository_instance.get_files_in_resource_set(100)
        assert empty_list == []
