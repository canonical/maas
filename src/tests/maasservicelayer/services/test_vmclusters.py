#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.vmcluster import VmClustersRepository
from maasservicelayer.services import VmClustersService


@pytest.mark.asyncio
class TestVmClusterService:
    async def test_move_to_zone(self) -> None:
        db_connection = Mock(AsyncConnection)
        vmcluster_repository_mock = Mock(VmClustersRepository)
        vmcluster_repository_mock.move_to_zone = AsyncMock()
        vmcluster_service = VmClustersService(
            db_connection, vmcluster_repository=vmcluster_repository_mock
        )
        await vmcluster_service.move_to_zone(0, 0)
        vmcluster_repository_mock.move_to_zone.assert_called_once_with(0, 0)
