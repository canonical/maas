#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.nodes import NodesRepository
from maasservicelayer.services import NodesService
from maasservicelayer.services.secrets import SecretsService


@pytest.mark.asyncio
class TestNodesService:
    async def test_move_to_zone(self) -> None:
        db_connection = Mock(AsyncConnection)
        secrets_service_mock = Mock(SecretsService)
        nodes_repository_mock = Mock(NodesRepository)
        nodes_repository_mock.move_to_zone = AsyncMock()
        nodes_service = NodesService(
            db_connection,
            secrets_service=secrets_service_mock,
            nodes_repository=nodes_repository_mock,
        )
        await nodes_service.move_to_zone(0, 0)
        nodes_repository_mock.move_to_zone.assert_called_once_with(0, 0)

    async def test_move_bmcs_to_zone(self) -> None:
        db_connection = Mock(AsyncConnection)
        secrets_service_mock = Mock(SecretsService)
        nodes_repository_mock = Mock(NodesRepository)
        nodes_repository_mock.move_bmcs_to_zone = AsyncMock()
        nodes_service = NodesService(
            db_connection,
            secrets_service=secrets_service_mock,
            nodes_repository=nodes_repository_mock,
        )
        await nodes_service.move_bmcs_to_zone(0, 0)
        nodes_repository_mock.move_bmcs_to_zone.assert_called_once_with(0, 0)

    async def test_get_bmc(self) -> None:
        db_connection = Mock(AsyncConnection)
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock()
        nodes_repository_mock = Mock(NodesRepository)
        nodes_repository_mock.get_node_bmc = AsyncMock()
        nodes_service = NodesService(
            db_connection,
            secrets_service=secrets_service_mock,
            nodes_repository=nodes_repository_mock,
        )
        await nodes_service.get_bmc("aaaaaa")
        nodes_repository_mock.get_node_bmc.assert_called_once_with("aaaaaa")
        secrets_service_mock.get_composite_secret.assert_called_once()
