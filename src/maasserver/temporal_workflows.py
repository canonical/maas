from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import activity, workflow

# This is a PoC code for experiments.
# TODO delete once it's no longer needed.


@dataclass
class NodeDeployWorkflowParams:
    node_id: str
    osystem: Optional[str] = None
    distro_series: Optional[str] = None
    hwe_kernel: Optional[str] = None
    user_data: Optional[str] = None
    install_kvm: bool = False
    register_vmhost: bool = False
    enable_hw_sync: bool = False


@workflow.defn(sandboxed=False)
class NodeDeployWorkflow:
    @workflow.run
    async def run(self, params: NodeDeployWorkflowParams) -> str:
        await workflow.execute_activity(
            acquire, params, schedule_to_close_timeout=timedelta(seconds=5)
        )


@activity.defn
async def acquire(activity_params: dict):
    print("[TEMPORAL] ACQUIRE ACTIVITY CALLED!", activity_params)
