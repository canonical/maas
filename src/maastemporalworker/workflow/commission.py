# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from temporalio import workflow
from temporalio.exceptions import ApplicationError

from maascommon.workflows.commission import (
    COMMISSION_WORKFLOW_NAME,
    CommissionParam,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.operation import (
    workflow_run_with_tracked_operation,
)
from maastemporalworker.workflow.utils import activity_defn_with_context

PREPARE_COMMISSIONING_ACTIVITY_NAME = "prepare-commissioning"


@dataclass
class PrepareCommissioningParam:
    system_id: str
    skip_networking: bool = False


class CommissionActivity(ActivityBase):
    @activity_defn_with_context(name=PREPARE_COMMISSIONING_ACTIVITY_NAME)
    async def prepare_commissioning(
        self, param: PrepareCommissioningParam
    ) -> None:
        async with self.start_transaction() as services:
            node = await services.nodes.get_one(
                query=QuerySpec(
                    where=NodeClauseFactory.with_system_id(param.system_id)
                )
            )
            if node is None:
                raise ApplicationError(
                    f"Node {param.system_id} not found", non_retryable=True
                )
            if not param.skip_networking:
                await services.commissioning.clear_networking_configuration(
                    node
                )


@workflow.defn(name=COMMISSION_WORKFLOW_NAME, sandboxed=False)
class CommissionWorkflow:
    @workflow_run_with_tracked_operation
    async def run(self, param: CommissionParam) -> None:
        pass
