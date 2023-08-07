import asyncio
from collections import defaultdict
from unittest.mock import Mock

import pytest
from temporalio.api.workflowservice.v1 import (
    DescribeNamespaceResponse,
    RegisterNamespaceResponse,
)
from temporalio.worker import Worker as TemporalWorker

from maasserver.workflow.testing.dummy import DummyWorkflow
from maasserver.workflow.worker import get_client_async, Worker


@pytest.fixture
def mock_register_namespace_response():
    future = asyncio.Future()
    future.set_result(RegisterNamespaceResponse())
    return future


@pytest.fixture
def mock_describe_namespace_response():
    future = asyncio.Future()
    future.set_result(DescribeNamespaceResponse())
    return future


@pytest.fixture
def mock_temporal_client(
    mock_register_namespace_response, mock_describe_namespace_response
):
    client = Mock()
    client.config = lambda: defaultdict(list)
    client.service_client.workflow_service.register_namespace = (
        lambda _: mock_register_namespace_response
    )
    client.service_client.workflow_service.describe_namespace = (
        lambda _: mock_describe_namespace_response
    )
    return client


@pytest.fixture
def mock_temporal_connect(mocker, mock_temporal_client):
    return mocker.patch(
        "temporalio.client.Client.connect", return_value=mock_temporal_client
    )


class TestGetClient:
    @pytest.mark.asyncio
    async def test_get_client_async(self, mock_temporal_connect):
        client = await get_client_async()
        assert client is not None


class TestWorker:
    @pytest.mark.asyncio
    async def test_run(self, mock_temporal_connect, mocker):
        mocker.patch("temporalio.worker.Worker.__init__", return_value=None)
        mock_worker_run = mocker.patch(
            "temporalio.worker.Worker.run", return_value=None
        )
        wrkr = Worker(additional_workflows=[DummyWorkflow])
        await wrkr.run()
        assert isinstance(wrkr._worker, TemporalWorker)
        mock_worker_run.assert_called_once()
