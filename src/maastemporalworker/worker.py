# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Temporal Worker wrapper"""

import dataclasses
import os
from typing import Any

from google.protobuf.duration_pb2 import Duration
from temporalio.api.workflowservice.v1 import (
    DescribeNamespaceRequest,
    RegisterNamespaceRequest,
)
from temporalio.client import Client, TLSConfig
import temporalio.converter
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker as TemporalWorker

from maasserver.utils.asynchronous import async_retry
from maastemporalworker.encryptor import EncryptionCodec
from provisioningserver.certificates import get_maas_cluster_cert_paths
from provisioningserver.utils.env import MAAS_ID, MAAS_SHARED_SECRET

REGION_TASK_QUEUE = "region"
TEMPORAL_HOST = "localhost"
TEMPORAL_PORT = 5271
TEMPORAL_WORKFLOW_RETENTION = "259200s"  # tctl's default retention in seconds
TEMPORAL_NAMESPACE = "default"


@async_retry()
async def get_client_async() -> Client:
    maas_id = MAAS_ID.get()
    pid = os.getpid()
    cert_file, key_file, cacert_file = get_maas_cluster_cert_paths()

    with open(cert_file, "rb") as f:
        cert = f.read()
    with open(key_file, "rb") as f:
        key = f.read()
    with open(cacert_file, "rb") as f:
        cacert = f.read()

    return await Client.connect(
        f"{TEMPORAL_HOST}:{TEMPORAL_PORT}",
        identity=f"{maas_id}@region:{pid}",
        data_converter=dataclasses.replace(
            temporalio.converter.default(),
            payload_codec=EncryptionCodec(MAAS_SHARED_SECRET.get().encode()),
        ),
        tls=TLSConfig(
            domain="maas",
            server_root_ca_cert=cacert,
            client_cert=cert,
            client_private_key=key,
        ),
    )


class Worker:
    namespace_name = TEMPORAL_NAMESPACE
    _worker = None

    def __init__(
        self,
        client: Client | None = None,
        task_queue: str = REGION_TASK_QUEUE,
        workflows: list[Any] | None = None,
        activities: list[Any] | None = None,
    ):
        self._worker = None
        self._client = client
        self._task_queue = task_queue
        self._workflows = workflows or []
        self._activities = activities or []
        self._workflow_retention = Duration()
        self._workflow_retention.FromJsonString(TEMPORAL_WORKFLOW_RETENTION)

    @async_retry()
    async def _setup_namespace(self) -> None:
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

    async def run(self) -> None:
        self._client = self._client or await get_client_async()
        await self._setup_namespace()
        self._worker = TemporalWorker(
            self._client,
            task_queue=self._task_queue,
            workflows=self._workflows,
            activities=self._activities,
        )
        await self._worker.run()

    async def stop(self) -> None:
        if self._worker:
            await self._worker.shutdown()
