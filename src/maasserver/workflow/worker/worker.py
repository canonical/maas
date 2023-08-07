# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Temporal Worker wrapper"""

from google.protobuf.duration_pb2 import Duration
from temporalio.api.workflowservice.v1 import (
    DescribeNamespaceRequest,
    RegisterNamespaceRequest,
)
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker as TemporalWorker

from maasserver.utils.asynchronous import async_retry

REGION_TASK_QUEUE = "region-controller"
TEMPORAL_HOST = "localhost"
TEMPORAL_PORT = 7233
TEMPORAL_WORKFLOW_RETENTION = "259200s"  # tctl's default retention in seconds


async def get_client_async():
    _client = await Client.connect(f"{TEMPORAL_HOST}:{TEMPORAL_PORT}")
    return _client


class Worker:
    namespace_name = "default"
    _worker = None

    def __init__(self, additional_workflows=()):
        self._additional_workflows = additional_workflows
        self._workflow_retention = Duration()
        self._workflow_retention.FromJsonString(TEMPORAL_WORKFLOW_RETENTION)

    @async_retry()
    async def _setup_namespace(self):
        try:
            await self._client.service_client.workflow_service.describe_namespace(
                DescribeNamespaceRequest(
                    namespace=self.namespace_name,
                ),
            )
        except RPCError as e:
            if e.status == RPCStatusCode.NOT_FOUND:
                await self._client.service_client.workflow_service.register_namespace(
                    RegisterNamespaceRequest(
                        namespace=self.namespace_name,
                        workflow_execution_retention_period=self._workflow_retention,
                    ),
                )
            else:
                raise e

    @async_retry()
    async def _connect(self):
        self._client = await get_client_async()

    async def run(self):
        await self._connect()
        await self._setup_namespace()
        self._worker = TemporalWorker(
            self._client,
            task_queue=REGION_TASK_QUEUE,
            workflows=[] + list(self._additional_workflows),
            activities=[],
        )
        await self._worker.run()

    async def stop(self):
        if self._worker:
            await self._worker.shutdown()
