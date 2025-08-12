# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the set LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefilesync import (
    BootResourceFileSyncRepository,
)
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.models.bootresourcefilesync import BootResourceFileSync
from maasservicelayer.models.nodes import Node
from maasservicelayer.services.bootresourcefilesync import (
    BootResourceFileSyncService,
)
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
    def filesync_service(
        self,
        filesync_repo_mock,
        nodes_service_mock,
    ) -> BootResourceFileSyncService:
        return BootResourceFileSyncService(
            context=Context(),
            repository=filesync_repo_mock,
            nodes_service=nodes_service_mock,
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

    async def test_get_synced_regions_for_file(
        self,
        filesync_repo_mock: Mock,
        filesync_service: BootResourceFileSyncService,
    ) -> None:
        await filesync_service.get_synced_regions_for_file(1)
        filesync_repo_mock.get_synced_regions_for_file.assert_awaited_once_with(
            1
        )
