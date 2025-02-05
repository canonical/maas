#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import call, Mock

import pytest

from maascommon.enums.events import EventTypeEnum
from maascommon.enums.node import NodeStatus
from maascommon.enums.power import PowerState
from maascommon.enums.scriptresult import ScriptStatus
from maascommon.node import NODE_STATUS_LABELS
from maasservicelayer.builders.nodes import NodeBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.nodes import (
    NodeClauseFactory,
    NodesRepository,
)
from maasservicelayer.models.base import MaasBaseModel, ResourceBuilder
from maasservicelayer.models.nodes import Node
from maasservicelayer.services import (
    EventsService,
    NodesService,
    ScriptResultsService,
)
from maasservicelayer.services.base import BaseService
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
            events_service=Mock(EventsService),
            scriptresults_service=Mock(ScriptResultsService),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return Node(
            id=2,
            system_id="systemid",
            hostname="hostname",
            status=NodeStatus.NEW,
            power_state=PowerState.ON,
        )


@pytest.mark.asyncio
class TestNodesService:

    @pytest.fixture
    def secrets_service_mock(self) -> SecretsService:
        return Mock(SecretsService)

    @pytest.fixture
    def nodes_repository_mock(self) -> NodesRepository:
        return Mock(NodesRepository)

    @pytest.fixture
    def events_service_mock(self) -> EventsService:
        return Mock(EventsService)

    @pytest.fixture
    def scriptresults_service_mock(self) -> ScriptResultsService:
        return Mock(ScriptResultsService)

    @pytest.fixture
    def nodes_service(
        self,
        secrets_service_mock,
        nodes_repository_mock,
        events_service_mock,
        scriptresults_service_mock,
    ) -> NodesService:
        return NodesService(
            context=Context(),
            secrets_service=secrets_service_mock,
            nodes_repository=nodes_repository_mock,
            events_service=events_service_mock,
            scriptresults_service=scriptresults_service_mock,
        )

    async def test_update_by_system_id(
        self, nodes_service, nodes_repository_mock
    ) -> None:
        updated_node = Mock(Node)
        nodes_repository_mock.update_one.return_value = updated_node
        builder = Mock(ResourceBuilder)
        result = await nodes_service.update_by_system_id(
            system_id="xyzio", builder=builder
        )
        assert result == updated_node
        nodes_repository_mock.update_one.assert_called_once_with(
            query=QuerySpec(where=NodeClauseFactory.with_system_id("xyzio")),
            builder=builder,
        )

    async def test_move_to_zone(
        self, nodes_service, nodes_repository_mock
    ) -> None:
        await nodes_service.move_to_zone(0, 0)
        nodes_repository_mock.move_to_zone.assert_called_once_with(0, 0)

    async def test_move_bmcs_to_zone(
        self, nodes_service, nodes_repository_mock
    ) -> None:
        await nodes_service.move_bmcs_to_zone(0, 0)
        nodes_repository_mock.move_bmcs_to_zone.assert_called_once_with(0, 0)

    async def test_get_bmc(
        self, nodes_service, nodes_repository_mock, secrets_service_mock
    ) -> None:
        nodes_repository_mock.get_node_bmc.return_value = Mock()
        await nodes_service.get_bmc("aaaaaa")
        nodes_repository_mock.get_node_bmc.assert_called_once_with("aaaaaa")
        secrets_service_mock.get_composite_secret.assert_called_once()

    async def test_mark_failed(
        self,
        nodes_service,
        nodes_repository_mock,
        scriptresults_service_mock,
        events_service_mock,
    ):
        node = Node(
            id=2,
            system_id="systemid",
            hostname="hostname",
            status=NodeStatus.DEPLOYING,
            power_state=PowerState.ON,
            current_commissioning_script_set_id=100,
            current_installation_script_set_id=101,
            current_testing_script_set_id=102,
        )
        nodes_repository_mock.get_one.return_value = node
        error_msg = "error message"

        await nodes_service.mark_failed(
            node.system_id,
            message=error_msg,
            script_result_status=ScriptStatus.FAILED,
        )

        events_service_mock.record_event.assert_has_calls(
            [
                call(
                    node=node,
                    event_type=EventTypeEnum.REQUEST_NODE_MARK_FAILED_SYSTEM,
                    event_action="mark_failed",
                    event_description=error_msg,
                ),
                call(
                    node=node,
                    event_type=EventTypeEnum.NODE_CHANGED_STATUS,
                    event_description=f"From '{NODE_STATUS_LABELS[node.status]}' to '{NODE_STATUS_LABELS[NodeStatus.FAILED_DEPLOYMENT]}'",
                ),
            ]
        )

        scriptresults_service_mock.update_running_scripts.assert_called_once_with(
            scripts_sets=[
                node.current_commissioning_script_set_id,
                node.current_testing_script_set_id,
                node.current_installation_script_set_id,
            ],
            new_status=ScriptStatus.FAILED,
        )

        nodes_repository_mock.update_by_id.assert_called_once_with(
            node.id,
            builder=NodeBuilder(
                status=NodeStatus.FAILED_DEPLOYMENT,
                error_description=error_msg,
            ),
        )
