#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.node import NodeStatus
from maascommon.enums.power import PowerState
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.nodes import (
    NodeClauseFactory,
    NodesRepository,
)
from maasservicelayer.models.base import MaasBaseModel, ResourceBuilder
from maasservicelayer.models.nodes import Node
from maasservicelayer.services import NodesService
from maasservicelayer.services._base import BaseService
from maasservicelayer.services.secrets import SecretsService
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonNodesService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return NodesService(
            context=Context(),
            secrets_service=Mock(SecretsService),
            nodes_repository=Mock(NodesRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return Node(
            id=2,
            system_id="systemid",
            status=NodeStatus.NEW,
            power_state=PowerState.ON,
        )


@pytest.mark.asyncio
class TestNodesService:
    async def test_update_by_system_id(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        nodes_repository_mock = Mock(NodesRepository)
        updated_node = Mock(Node)
        nodes_repository_mock.update_one.return_value = updated_node
        nodes_service = NodesService(
            context=Context(),
            secrets_service=secrets_service_mock,
            nodes_repository=nodes_repository_mock,
        )
        builder = Mock(ResourceBuilder)
        result = await nodes_service.update_by_system_id(
            system_id="xyzio", builder=builder
        )
        assert result == updated_node
        nodes_repository_mock.update_one.assert_called_once_with(
            query=QuerySpec(where=NodeClauseFactory.with_system_id("xyzio")),
            builder=builder,
        )

    async def test_move_to_zone(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        nodes_repository_mock = Mock(NodesRepository)
        nodes_service = NodesService(
            context=Context(),
            secrets_service=secrets_service_mock,
            nodes_repository=nodes_repository_mock,
        )
        await nodes_service.move_to_zone(0, 0)
        nodes_repository_mock.move_to_zone.assert_called_once_with(0, 0)

    async def test_move_bmcs_to_zone(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        nodes_repository_mock = Mock(NodesRepository)
        nodes_service = NodesService(
            context=Context(),
            secrets_service=secrets_service_mock,
            nodes_repository=nodes_repository_mock,
        )
        await nodes_service.move_bmcs_to_zone(0, 0)
        nodes_repository_mock.move_bmcs_to_zone.assert_called_once_with(0, 0)

    async def test_get_bmc(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        nodes_repository_mock = Mock(NodesRepository)
        nodes_repository_mock.get_node_bmc.return_value = Mock()
        nodes_service = NodesService(
            context=Context(),
            secrets_service=secrets_service_mock,
            nodes_repository=nodes_repository_mock,
        )
        await nodes_service.get_bmc("aaaaaa")
        nodes_repository_mock.get_node_bmc.assert_called_once_with("aaaaaa")
        secrets_service_mock.get_composite_secret.assert_called_once()

    async def test_get_nodes_for_user(self) -> None:
        secrets_service_mock = Mock(SecretsService)
        nodes_repository_mock = Mock(NodesRepository)
        nodes_repository_mock.get_many.return_value = Mock()
        nodes_service = NodesService(
            context=Context(),
            secrets_service=secrets_service_mock,
            nodes_repository=nodes_repository_mock,
        )
        await nodes_service.get_nodes_for_user(1)
        nodes_repository_mock.get_many.assert_called_once_with(
            query=QuerySpec(where=NodeClauseFactory.with_owner_id(1))
        )
