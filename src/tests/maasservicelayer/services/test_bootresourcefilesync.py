# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the set LICENSE).

import math
from unittest.mock import Mock

import pytest

from maascommon.enums.boot_resources import BootResourceFileType
from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefilesync import (
    BootResourceFileSyncRepository,
)
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.models.bootresourcefilesync import BootResourceFileSync
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.models.nodes import Node
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresourcefilesync import (
    BootResourceFileSyncService,
)
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonBootResourceFileSyncService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootResourceFileSyncService:
        return BootResourceFileSyncService(
            context=Context(),
            repository=Mock(BootResourceFileSyncRepository),
            nodes_service=Mock(NodesService),
            bootresourcesets_service=Mock(BootResourceSetsService),
            bootresourcefiles_service=Mock(BootResourceFilesService),
        )

    @pytest.fixture
    def test_instance(self) -> BootResourceFileSync:
        now = utcnow()
        return BootResourceFileSync(
            id=1,
            created=now,
            updated=now,
            size=100,
            file_id=1,
            region_id=1,
        )


@pytest.mark.asyncio
class TestBootResourceFileSyncService:
    @pytest.fixture
    def filesync_repo_mock(self) -> Mock:
        return Mock(BootResourceFileSyncRepository)

    @pytest.fixture
    def nodes_service_mock(self) -> Mock:
        return Mock(NodesService)

    @pytest.fixture
    def resourcesets_service_mock(self) -> Mock:
        return Mock(BootResourceSetsService)

    @pytest.fixture
    def resourcefiles_service_mock(self) -> Mock:
        return Mock(BootResourceFilesService)

    @pytest.fixture
    def filesync_service(
        self,
        filesync_repo_mock,
        nodes_service_mock,
        resourcesets_service_mock,
        resourcefiles_service_mock,
    ) -> BootResourceFileSyncService:
        return BootResourceFileSyncService(
            context=Context(),
            repository=filesync_repo_mock,
            nodes_service=nodes_service_mock,
            bootresourcesets_service=resourcesets_service_mock,
            bootresourcefiles_service=resourcefiles_service_mock,
        )

    async def test_get_regions_count(
        self,
        nodes_service_mock: Mock,
        filesync_service: BootResourceFileSyncService,
    ) -> None:
        nodes_service_mock.get_many.return_value = [Mock(Node)]
        n_regions = await filesync_service.get_regions_count()
        assert n_regions == 1
        nodes_service_mock.get_many.assert_called_once_with(
            query=QuerySpec(
                where=NodeClauseFactory.or_clauses(
                    [
                        NodeClauseFactory.with_type(
                            NodeTypeEnum.REGION_CONTROLLER
                        ),
                        NodeClauseFactory.with_type(
                            NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                        ),
                    ]
                )
            )
        )

    async def test_get_current_size_for_files(
        self,
        filesync_repo_mock: Mock,
        filesync_service: BootResourceFileSyncService,
    ) -> None:
        await filesync_service.get_current_sync_size_for_files({1})
        filesync_repo_mock.get_current_sync_size_for_files.assert_called_once_with(
            {1}
        )

    @pytest.mark.parametrize(
        "synced_size, expected_progress, expected_complete",
        [
            (0, 0.0, False),
            (100, 100.0, True),
            (50, 50.0, False),
        ],
    )
    async def test_file_sync_progress(
        self,
        synced_size: int,
        expected_progress: float,
        expected_complete: bool,
        filesync_repo_mock: Mock,
        nodes_service_mock: Mock,
        resourcefiles_service_mock: Mock,
        filesync_service: BootResourceFileSyncService,
    ) -> None:
        nodes_service_mock.get_many.return_value = [Mock(Node)]
        resourcefiles_service_mock.get_by_id.return_value = BootResourceFile(
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
        filesync_repo_mock.get_current_sync_size_for_files.return_value = (
            synced_size
        )
        sync_progress = await filesync_service.file_sync_progress(1)
        assert math.isclose(sync_progress, expected_progress)
        sync_complete = await filesync_service.file_sync_complete(1)
        assert sync_complete is expected_complete

        resourcefiles_service_mock.get_by_id.assert_called_with(1)
        filesync_repo_mock.get_current_sync_size_for_files.assert_called_with(
            {1}
        )

    @pytest.mark.parametrize(
        "synced_size, expected_progress, expected_complete",
        [
            (0, 0.0, False),
            (300, 100.0, True),
            (100, 33.333333333, False),
            (270, 90.00, False),
        ],
    )
    async def test_resource_set_sync_progress(
        self,
        synced_size: int,
        expected_progress: float,
        expected_complete: bool,
        filesync_repo_mock: Mock,
        nodes_service_mock: Mock,
        resourcefiles_service_mock: Mock,
        resourcesets_service_mock: Mock,
        filesync_service: BootResourceFileSyncService,
    ) -> None:
        resourcesets_service_mock.get_by_id.return_value = Mock(
            BootResourceSet
        )
        nodes_service_mock.get_many.return_value = [Mock(Node)]
        resourcefiles_service_mock.get_files_in_resource_set.return_value = [
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
        filesync_repo_mock.get_current_sync_size_for_files.return_value = (
            synced_size
        )
        sync_progress = await filesync_service.resource_set_sync_progress(1)
        assert math.isclose(sync_progress, expected_progress)
        sync_complete = await filesync_service.resource_set_sync_complete(1)
        assert sync_complete is expected_complete

        resourcesets_service_mock.get_by_id.assert_called_with(1)
        resourcefiles_service_mock.get_files_in_resource_set.assert_called_with(
            1
        )
        filesync_repo_mock.get_current_sync_size_for_files.assert_called_with(
            {0, 1, 2}
        )
