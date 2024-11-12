# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from temporalio import workflow
from temporalio.common import RetryPolicy

from maascommon.workflows.commission import (
    COMMISSION_N_WORKFLOW_NAME,
    COMMISSION_WORKFLOW_NAME,
    CommissionNParam,
)


@workflow.defn(name=COMMISSION_N_WORKFLOW_NAME, sandboxed=False)
class CommissionNWorkflow:
    @workflow.run
    async def run(self, params: CommissionNParam) -> None:
        for param in params.params:
            await workflow.execute_child_workflow(
                COMMISSION_WORKFLOW_NAME,
                param,
                id=f"commission:{param.system_id}",
                task_queue=param.queue,
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
