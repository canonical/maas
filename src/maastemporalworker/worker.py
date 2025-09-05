# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Temporal Worker wrapper"""

import dataclasses
import os
from typing import Any

from google.protobuf.duration_pb2 import Duration
from temporalio import workflow
from temporalio.api.workflowservice.v1 import (
    DescribeNamespaceRequest,
    RegisterNamespaceRequest,
)
from temporalio.client import Client, TLSConfig
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker as TemporalWorker
from temporalio.worker.workflow_sandbox import (
    SandboxedWorkflowRunner,
    SandboxRestrictions,
)

from maastemporalworker.encryptor import EncryptionCodec
from maastemporalworker.workflow.utils import async_retry
from provisioningserver.certificates import get_maas_cluster_cert_paths
from provisioningserver.utils.env import MAAS_ID, MAAS_SHARED_SECRET

with workflow.unsafe.imports_passed_through():
    from maastemporalworker.converter import pydantic_data_converter

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
            # TODO: Replace this when we switch to Pydantic 2.x
            pydantic_data_converter,
            payload_codec=EncryptionCodec(MAAS_SHARED_SECRET.get().encode()),
        ),
        tls=TLSConfig(
            domain="maas",
            server_root_ca_cert=cacert,
            client_cert=cert,
            client_private_key=key,
        ),
    )


# See https://github.com/temporalio/samples-python/blob/3bd017d6048cef8da5dc2c95c37c759e7203a7ba/pydantic_converter_v1/worker.py
# Due to known issues with Pydantic's use of issubclass and our inability to
# override the check in sandbox, Pydantic will think datetime is actually date
# in the sandbox. At the expense of protecting against datetime.now() use in
# workflows, we're going to remove datetime module restrictions. See sdk-python
# README's discussion of known sandbox issues for more details.
def custom_sandbox_runner() -> SandboxedWorkflowRunner:
    invalid_module_member_children = dict(
        SandboxRestrictions.invalid_module_members_default.children
    )
    del invalid_module_member_children["datetime"]
    return SandboxedWorkflowRunner(
        restrictions=dataclasses.replace(
            SandboxRestrictions.default,
            invalid_module_members=dataclasses.replace(
                SandboxRestrictions.invalid_module_members_default,
                children=invalid_module_member_children,
            ),
        )
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
            workflow_runner=custom_sandbox_runner(),
        )
        await self._worker.run()

    async def stop(self) -> None:
        if self._worker:
            await self._worker.shutdown()
