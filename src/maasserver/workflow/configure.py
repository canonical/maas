from dataclasses import dataclass

from temporalio import workflow


@dataclass
class ConfigureWorkerPoolInput:
    system_id: str


@workflow.defn(name="configure_worker_pool", sandboxed=False)
class ConfigureWorkerPoolWorkflow:
    """A ConfigureWorkerPool workflow to setup MAAS Agent workers"""

    @workflow.run
    async def run(self, input: ConfigureWorkerPoolInput) -> None:
        # Check configuration and spawn required child workflows
        # as an example we add VLAN workers:
        return await workflow.execute_child_workflow(
            workflow="add_worker",
            task_queue=input.system_id,
            arg={"task_queue": "vlan0", "workflows": ["check_ip"]},
        )
