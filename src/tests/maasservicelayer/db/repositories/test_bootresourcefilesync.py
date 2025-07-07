# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the filesync LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maasservicelayer.builders.bootresourcefilesync import (
    BootResourceFileSyncBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresourcefilesync import (
    BootResourceFileSyncRepository,
)
from maasservicelayer.models.bootresourcefilesync import BootResourceFileSync
from tests.fixtures.factories.bootresourcefiles import (
    create_test_bootresourcefile_entry,
)
from tests.fixtures.factories.bootresourcefilesync import (
    create_test_bootresourcefilesync_entry,
)
from tests.fixtures.factories.bootresources import (
    create_test_bootresource_entry,
)
from tests.fixtures.factories.bootresourcesets import (
    create_test_bootresourceset_entry,
)
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestBootResourceFileSyncRepository(
    RepositoryCommonTests[BootResourceFileSync]
):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[BootResourceFileSync]:
        return [
            await create_test_bootresourcefilesync_entry(
                fixture, size=100, file_id=i, region_id=i
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> BootResourceFileSync:
        return await create_test_bootresourcefilesync_entry(
            fixture, size=100, file_id=1, region_id=1
        )

    @pytest.fixture
    async def instance_builder(
        self, *args, **kwargs
    ) -> BootResourceFileSyncBuilder:
        return BootResourceFileSyncBuilder(size=100, file_id=1, region_id=1)

    @pytest.fixture
    async def instance_builder_model(
        self,
    ) -> type[BootResourceFileSyncBuilder]:
        return BootResourceFileSyncBuilder

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> BootResourceFileSyncRepository:
        return BootResourceFileSyncRepository(
            Context(connection=db_connection)
        )

    async def test_get_current_sync_size_for_files(
        self,
        repository_instance: BootResourceFileSyncRepository,
        fixture: Fixture,
    ) -> None:
        boot_resource = await create_test_bootresource_entry(
            fixture,
            rtype=BootResourceType.SYNCED,
            name="ubuntu/noble",
            architecture="amd64/generic",
        )
        resource_set = await create_test_bootresourceset_entry(
            fixture,
            version="20250618",
            label="stable",
            resource_id=boot_resource.id,
        )
        files = []
        for i in range(3):
            files.append(
                await create_test_bootresourcefile_entry(
                    fixture,
                    filename=f"filename-{i}",
                    filetype=BootResourceFileType.SQUASHFS_IMAGE,
                    sha256=f"abcdef{i}",
                    filename_on_disk=f"abcdef{i}",
                    size=100,
                    resource_set_id=resource_set.id,
                )
            )
            await create_test_bootresourcefilesync_entry(
                fixture,
                size=50,
                file_id=files[i].id,
                region_id=1,
            )
        file_ids = {file.id for file in files}
        current_size = (
            await repository_instance.get_current_sync_size_for_files(file_ids)
        )
        assert current_size == 50 * 3

        # only select two files
        file_ids.pop()
        current_size = (
            await repository_instance.get_current_sync_size_for_files(file_ids)
        )
        assert current_size == 50 * 2

    async def test_get_current_sync_size_for_files_no_files(
        self,
        repository_instance: BootResourceFileSyncRepository,
    ) -> None:
        file_ids = {1, 2}
        current_size = (
            await repository_instance.get_current_sync_size_for_files(file_ids)
        )
        assert current_size == 0
