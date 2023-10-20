# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Temporal Worker wrapper"""

import dataclasses

from google.protobuf.duration_pb2 import Duration
from temporalio.api.workflowservice.v1 import (
    DescribeNamespaceRequest,
    RegisterNamespaceRequest,
)
from temporalio.client import Client
import temporalio.converter
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker as TemporalWorker

from maasserver.utils.asynchronous import async_retry
from maasserver.workflow.codec.encryptor import EncryptionCodec
from provisioningserver.utils.env import MAAS_SHARED_SECRET

REGION_TASK_QUEUE = "region_controller"
TEMPORAL_HOST = "localhost"
TEMPORAL_PORT = 5271
TEMPORAL_WORKFLOW_RETENTION = "259200s"  # tctl's default retention in seconds

_client = None


@async_retry()
async def get_client_async():
    global _client
    if not _client:
        _client = await Client.connect(
            f"{TEMPORAL_HOST}:{TEMPORAL_PORT}",
            data_converter=dataclasses.replace(
                temporalio.converter.default(),
                payload_codec=EncryptionCodec(
                    MAAS_SHARED_SECRET.get().encode()
                ),
            ),
        )
    return _client


class Worker:
    namespace_name = "default"
    _worker = None

    def __init__(
        self,
        client=None,
        task_queue=REGION_TASK_QUEUE,
        workflows=None,
        activities=None,
    ):
        self._client = client
        self._task_queue = task_queue
        self._workflows = [] if workflows is None else workflows
        self._activities = [] if activities is None else activities
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

    async def run(self):
        self._client = (
            await get_client_async() if self._client is None else self._client
        )
        await self._setup_namespace()
        self._worker = TemporalWorker(
            self._client,
            task_queue=self._task_queue,
            workflows=self._workflows,
            activities=self._activities,
        )
        await self._worker.run()

    async def stop(self):
        if self._worker:
            await self._worker.shutdown()
