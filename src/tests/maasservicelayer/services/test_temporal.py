from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.client import Client

from maasservicelayer.context import Context
from maasservicelayer.services.temporal import (
    TemporalService,
    TemporalServiceCache,
)


@pytest.mark.asyncio
class TestTemporalService:
    async def test_post_commit(self):
        mock_connection = Mock(AsyncConnection)
        mock_connection.closed = False
        mock_temporal = Mock(Client)
        service = TemporalService(
            context=Context(),
            cache=TemporalServiceCache(temporal_client=mock_temporal),
        )

        service.register_workflow_call(
            "test_workflow", None, workflow_id="abc"
        )

        await service.post_commit()

        mock_temporal.execute_workflow.assert_called_once_with(
            "test_workflow", None, id="abc", task_queue="region"
        )

    async def test_workflow_is_registered(self):
        service = TemporalService(
            context=Context(),
            cache=TemporalServiceCache(temporal_client=Mock(Client)),
        )

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

    async def test_register_workflow_call(self):
        service = TemporalService(
            context=Context(),
            cache=TemporalServiceCache(temporal_client=Mock(Client)),
        )

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

    async def test_register_or_update_workflow_call_override_parameters(self):
        service = TemporalService(
            context=Context(),
            cache=TemporalServiceCache(temporal_client=Mock(Client)),
        )

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

    async def test_register_or_update_workflow_call_merge_parameters(self):
        service = TemporalService(
            context=Context(),
            cache=TemporalServiceCache(temporal_client=Mock(Client)),
        )

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
