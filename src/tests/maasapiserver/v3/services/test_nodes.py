from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.nodes import NodesRepository
from maasapiserver.v3.services import NodesService


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
