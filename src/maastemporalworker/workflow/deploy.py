# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from temporalio import workflow
from temporalio.common import RetryPolicy


@dataclass
class DeployParam:
    system_id: str
    queue: str


@dataclass
class DeployNParam:
    params: list[DeployParam]


@workflow.defn(name="DeployNWorkflow", sandboxed=False)
class DeployNWorkflow:
    @workflow.run
    async def run(self, params: DeployNParam) -> None:
        for param in params.params:
            await workflow.execute_child_workflow(
                "deploy",
                param,
                id=f"deploy:{param.system_id}",
                task_queue=param.queue,
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
