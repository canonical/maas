from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.workflow import ParentClosePolicy

from maasserver.workflow.api_activities import GetRackControllerInput


@dataclass
class ConfigureWorkerPoolInput:
    system_id: str


@workflow.defn(name="configure_worker_pool", sandboxed=False)
class ConfigureWorkerPoolWorkflow:
    """A ConfigureWorkerPool workflow to setup MAAS Agent workers"""

    @workflow.run
    async def run(self, input: ConfigureWorkerPoolInput) -> None:
        result = await workflow.execute_activity(
            "get-rack-controller",
            GetRackControllerInput(input.system_id),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                backoff_coefficient=2.0,
                maximum_attempts=5,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=2),
            ),
        )

        interface_set = result["interface_set"]
        vlan_ids = set(
            [n["vlan"]["id"] for n in interface_set if n.get("vlan")]
        )

        for vlan_id in vlan_ids:
            workflow_id = (
                f"add-worker:{input.system_id}:task_queue:vlan-{vlan_id}"
            )

            existing = workflow.get_external_workflow_handle(workflow_id)
            if existing and existing.run_id:
                continue

            # If you need to extend workflows/activities that should be
            # registered, ensure they are allowed by the worker pool
            await workflow.start_child_workflow(
                id=workflow_id,
                parent_close_policy=ParentClosePolicy.ABANDON,
                workflow="add_worker",
                task_queue=f"agent:{input.system_id}",
                arg={
                    "task_queue": f"vlan-{vlan_id}",
                    "workflows": [
                        "check_ip",
                        "power_query",
                        "power_cycle",
                        "power_on",
                        "power_off",
                    ],
                    "activities": [
                        "power",
                    ],
                },
            )
