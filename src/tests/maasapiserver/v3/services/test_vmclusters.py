from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.bmc import BmcRepository
from maasapiserver.v3.services import VmClustersService


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestVmClusterService:
    async def test_move_to_zone(self, db_connection: AsyncConnection) -> None:
        vmcluster_repository_mock = Mock(BmcRepository)
        vmcluster_repository_mock.move_to_zone = AsyncMock()
        vmcluster_service = VmClustersService(
            db_connection, vmcluster_repository=vmcluster_repository_mock
        )
        await vmcluster_service.move_to_zone(0, 0)
        vmcluster_repository_mock.move_to_zone.assert_called_once_with(0, 0)
