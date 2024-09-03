#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.bmc import BmcRepository
from maasservicelayer.services import BmcService


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
