from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.services import BmcService
from maasservicelayer.db.repositories.bmc import BmcRepository


@pytest.mark.asyncio
class TestBmcService:
    async def test_move_to_zone(self) -> None:
        db_connection = Mock(AsyncConnection)
        bmc_repository_mock = Mock(BmcRepository)
        bmc_repository_mock.move_to_zone = AsyncMock()
        bmc_service = BmcService(
            db_connection, bmc_repository=bmc_repository_mock
        )
        await bmc_service.move_to_zone(0, 0)
        bmc_repository_mock.move_to_zone.assert_called_once_with(0, 0)
