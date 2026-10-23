# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from temporalio import workflow
from temporalio.common import RetryPolicy

from maascommon.workflows.commission import (
    COMMISSION_N_WORKFLOW_NAME,
    COMMISSION_WORKFLOW_NAME,
    CommissionNParam,
    CommissionParam,
)
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)


class CommissionActivity(ActivityBase):
    @activity_defn_with_context
    def prepare_commissioning(self) -> None:
        pass

    @activity_defn_with_context
    def resolve_power_rack_target(self) -> None:
        pass

    @activity_defn_with_context
    def finalize_commissioning(self) -> None:
        pass


@workflow.defn(name=COMMISSION_WORKFLOW_NAME, sandboxed=False)
class CommissionWorkflow:
    @workflow_run_with_context
    async def run(self, param: CommissionParam) -> None:
        pass
