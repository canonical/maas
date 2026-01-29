# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.client import (
    Client,
    WorkflowExecutionDescription,
    WorkflowExecutionStatus,
    WorkflowHandle,
)

from maasservicelayer.context import Context
from maasservicelayer.services.temporal import (
    TemporalService,
    TemporalServiceCache,
)


@pytest.mark.asyncio
class TestTemporalService:
    @pytest.fixture
    def temporal_client_mock(self):
        return Mock(Client)

    @pytest.fixture
    def service(self, temporal_client_mock):
        return TemporalService(
            context=Context(),
            cache=TemporalServiceCache(temporal_client=temporal_client_mock),
        )

    @pytest.fixture
    def workflow_handle_mock(self, temporal_client_mock: Mock):
        handle = Mock(WorkflowHandle)
        temporal_client_mock.get_workflow_handle.return_value = handle
        return handle

    async def test_post_commit(
        self, service: TemporalService, temporal_client_mock
    ):
        mock_connection = Mock(AsyncConnection)
        mock_connection.closed = False

        param = {"a": 1}

        service.register_workflow_call(
            "test_workflow", parameter=param, workflow_id="abc"
        )

        await service.post_commit()

        temporal_client_mock.execute_workflow.assert_called_once_with(
            "test_workflow", param, id="abc", task_queue="region"
        )

    async def test_post_commit_without_parameter(
        self, service: TemporalService, temporal_client_mock
    ):
        mock_connection = Mock(AsyncConnection)
        mock_connection.closed = False

        service.register_workflow_call("test_workflow", workflow_id="abc")

        await service.post_commit()

        temporal_client_mock.execute_workflow.assert_called_once_with(
            "test_workflow", id="abc", task_queue="region"
        )

    async def test_workflow_is_registered(self, service: TemporalService):
        assert not service.workflow_is_registered("test_workflow")
        assert not service.workflow_is_registered(
            "test_workflow", workflow_id="abc"
        )

        service.register_workflow_call(
            "test_workflow", None, workflow_id="abc"
        )

        assert not service.workflow_is_registered("test_workflow")
        assert not service.workflow_is_registered(
            "test_workflow", workflow_id="def"
        )
        assert service.workflow_is_registered(
            "test_workflow", workflow_id="abc"
        )

    async def test_register_workflow_call(self, service: TemporalService):
        assert not service.workflow_is_registered("test_workflow")
        assert not service.workflow_is_registered(
            "test_workflow", workflow_id="abc"
        )

        service.register_workflow_call(
            "test_workflow", None, workflow_id="abc"
        )

        assert not service.workflow_is_registered("test_workflow")
        assert service.workflow_is_registered(
            "test_workflow", workflow_id="abc"
        )

    async def test_register_or_update_workflow_call_override_parameters(
        self, service: TemporalService
    ):
        service.register_workflow_call(
            "test_workflow", None, workflow_id="abc"
        )

        parameter = {"a": 1, "b": 2}

        service.register_or_update_workflow_call(
            "test_workflow",
            parameter,
            workflow_id="abc",
            override_previous_parameters=True,
        )

        assert (
            service._post_commit_workflows["test_workflow:abc"][1] == parameter
        )

    async def test_register_or_update_workflow_call_merge_parameters(
        self, service: TemporalService
    ):
        parameter = {"a": 1, "b": 2}

        service.register_workflow_call(
            "test_workflow", parameter, workflow_id="abc"
        )

        new_parameter = {"a": 3, "c": 4}

        def merge_func(
            old: dict[str, Any], new: dict[str, Any]
        ) -> dict[str, Any]:
            for k, v in new.items():
                old[k] = v
            return old

        service.register_or_update_workflow_call(
            "test_workflow",
            new_parameter,
            workflow_id="abc",
            parameter_merge_func=merge_func,
        )

        assert service._post_commit_workflows["test_workflow:abc"][1] == {
            "a": 3,
            "b": 2,
            "c": 4,
        }

    async def test_query_workflow(
        self,
        service: TemporalService,
        temporal_client_mock,
        workflow_handle_mock,
    ) -> None:
        await service.query_workflow("wf-id", "query")
        temporal_client_mock.get_workflow_handle.assert_called_once_with(
            "wf-id"
        )
        workflow_handle_mock.query.assert_awaited_once_with("query")

    async def test_cancel_workflow(
        self,
        service: TemporalService,
        temporal_client_mock,
        workflow_handle_mock,
    ) -> None:
        await service.cancel_workflow("wf-id")
        temporal_client_mock.get_workflow_handle.assert_called_once_with(
            "wf-id"
        )
        workflow_handle_mock.cancel.assert_awaited_once()

    async def test_terminate_workflow(
        self,
        service: TemporalService,
        temporal_client_mock,
        workflow_handle_mock,
    ) -> None:
        await service.terminate_workflow("wf-id")
        temporal_client_mock.get_workflow_handle.assert_called_once_with(
            "wf-id"
        )
        workflow_handle_mock.terminate.assert_awaited_once()

    async def test_workflow_status(
        self,
        service: TemporalService,
        temporal_client_mock,
        workflow_handle_mock,
    ) -> None:
        exec_description = Mock(WorkflowExecutionDescription)
        exec_description.status = WorkflowExecutionStatus.RUNNING
        workflow_handle_mock.describe.return_value = exec_description

        await service.workflow_status("wf-id")
        temporal_client_mock.get_workflow_handle.assert_called_once_with(
            "wf-id"
        )
        workflow_handle_mock.describe.assert_awaited_once()
