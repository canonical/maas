# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from collections import defaultdict
from unittest.mock import Mock

import pytest
from temporalio import workflow
from temporalio.api.workflowservice.v1 import (
    DescribeNamespaceResponse,
    RegisterNamespaceResponse,
)
from temporalio.worker import Worker as TemporalWorker

from maastemporalworker.worker import get_client_async, Worker
from provisioningserver.utils.env import MAAS_ID, MAAS_SHARED_SECRET


@workflow.defn(name="DummyWorkflow", sandboxed=False)
class DummyWorkflow:
    """A no-op workflow for test purposes"""

    @workflow.run
    async def run(self) -> None:
        return


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


class TestGetClientAsync:
    @pytest.mark.asyncio
    async def test_brackets_ipv6_connect_address(
        self, mocker, tmp_path, mock_temporal_client
    ):
        """The host:port string passed to Client.connect() must bracket
        IPv6 addresses (e.g. `[fd00::1]:5271`), or the Temporal SDK fails
        to parse it."""
        for name in ("cert.pem", "key.pem", "cacert.pem"):
            (tmp_path / name).write_bytes(b"dummy")
        mocker.patch(
            "maastemporalworker.worker.get_maas_cluster_cert_paths",
            return_value=(
                str(tmp_path / "cert.pem"),
                str(tmp_path / "key.pem"),
                str(tmp_path / "cacert.pem"),
            ),
        )
        mocker.patch(
            "maastemporalworker.worker.get_temporal_connect_address",
            return_value="fd00::1",
        )
        mock_connect = mocker.patch(
            "temporalio.client.Client.connect",
            return_value=mock_temporal_client,
        )
        MAAS_ID.set("system-id")
        MAAS_SHARED_SECRET.set("x" * 32)

        await get_client_async()

        target_host_port = mock_connect.call_args[0][0]
        assert target_host_port == "[fd00::1]:5271"
