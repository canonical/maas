# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from collections import defaultdict
from unittest.mock import AsyncMock, Mock, patch

import pytest
from temporalio import workflow
from temporalio.api.workflowservice.v1 import (
    DescribeNamespaceResponse,
    RegisterNamespaceResponse,
)
from temporalio.worker import Worker as TemporalWorker

from maascommon.workflows.interceptors import ContextPropagationInterceptor
from maastemporalworker.worker import Worker
from provisioningserver.utils.env import MAAS_SHARED_SECRET


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


class TestGetClientAsync:
    @pytest.mark.asyncio
    @patch("maastemporalworker.worker.MAAS_SHARED_SECRET")
    @patch("maastemporalworker.worker.MAAS_ID")
    @patch("maastemporalworker.worker.get_maas_cluster_cert_paths")
    async def test_get_client_async_reads_files_and_returns_client(
        self,
        mock_get_maas_cluster_cert_paths,
        mock_maas_id,
        mock_maas_shared_secret,
        tmp_path,
    ):
        cert_file = tmp_path / "cert.pem"
        key_file = tmp_path / "key.pem"
        ca_file = tmp_path / "ca.pem"

        cert_file.write_bytes(b"fake-cert")
        key_file.write_bytes(b"fake-key")
        ca_file.write_bytes(b"fake-ca")

        mock_get_maas_cluster_cert_paths.return_value = (
            str(cert_file),
            str(key_file),
            str(ca_file),
        )

        mock_maas_shared_secret.get.return_value = "x" * 32
        mock_maas_id.get.return_value = "maas-id"

        with patch(
            "maastemporalworker.worker.Client.connect", new_callable=AsyncMock
        ) as mock_connect:
            fake_client = object()
            mock_connect.return_value = fake_client

            from maastemporalworker.worker import get_client_async

            client = await get_client_async()
            assert client is fake_client

            mock_connect.assert_awaited_once()

            _, kwargs = mock_connect.call_args
            assert "tls" in kwargs
            assert kwargs["identity"].startswith("maas-id@region:")
            assert any(
                "ContextPropagationInterceptor" in str(type(i))
                for i in kwargs["interceptors"]
            ), "Interceptors should have ContextPropagationInterceptor"


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

    @pytest.mark.asyncio
    async def test_run_includes_context_propagation_interceptor(
        self, mock_temporal_client
    ):
        with patch(
            "maastemporalworker.worker.TemporalWorker"
        ) as mock_temporal_worker_cls:
            mock_temporal_worker_cls.return_value.run = AsyncMock(
                return_value=None
            )

            wrkr = Worker(
                client=mock_temporal_client, workflows=[DummyWorkflow]
            )
            await wrkr.run()

            assert mock_temporal_worker_cls.call_count == 1, (
                "TemporalWorker should be instantiated once"
            )

            _, kwargs = mock_temporal_worker_cls.call_args
            interceptors = kwargs.get("interceptors", [])

            assert any(
                isinstance(i, ContextPropagationInterceptor)
                for i in interceptors
            ), (
                "ContextPropagationInterceptor must be included in Worker interceptors"
            )
