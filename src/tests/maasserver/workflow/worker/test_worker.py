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
from maasserver.workflow.worker import Worker
from provisioningserver.utils.env import MAAS_SHARED_SECRET


@pytest.fixture
async def mock_register_namespace_response():
    future = asyncio.Future()
    future.set_result(RegisterNamespaceResponse())
    return future


@pytest.fixture
async def mock_describe_namespace_response():
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


class TestWorker:
    @pytest.mark.asyncio
    async def test_run(self, mocker, mock_temporal_client):
        mocker.patch("temporalio.worker.Worker.__init__", return_value=None)
        mock_worker_run = mocker.patch(
            "temporalio.worker.Worker.run", return_value=None
        )

        MAAS_SHARED_SECRET.set("x" * 32)

        wrkr = Worker(client=mock_temporal_client, workflows=[DummyWorkflow])
        await wrkr.run()

        assert isinstance(wrkr._worker, TemporalWorker)
        mock_worker_run.assert_called_once()
