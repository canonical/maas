#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.nodes import NodesRepository
from maasservicelayer.services import NodesService


@pytest.mark.asyncio
class TestNodesService:
    async def test_move_to_zone(self) -> None:
        db_connection = Mock(AsyncConnection)
        nodes_repository_mock = Mock(NodesRepository)
        nodes_repository_mock.move_to_zone = AsyncMock()
        nodes_service = NodesService(
            db_connection, nodes_repository=nodes_repository_mock
        )
        await nodes_service.move_to_zone(0, 0)
        nodes_repository_mock.move_to_zone.assert_called_once_with(0, 0)

    async def test_move_bmcs_to_zone(self) -> None:
        db_connection = Mock(AsyncConnection)
        nodes_repository_mock = Mock(NodesRepository)
        nodes_repository_mock.move_bmcs_to_zone = AsyncMock()
        nodes_service = NodesService(
            db_connection, nodes_repository=nodes_repository_mock
        )
        await nodes_service.move_bmcs_to_zone(0, 0)
        nodes_repository_mock.move_bmcs_to_zone.assert_called_once_with(0, 0)
