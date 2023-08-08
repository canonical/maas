from dataclasses import dataclass

from temporalio import workflow


@dataclass
class ConfigureInput:
    system_id: str


@workflow.defn(name="Configure", sandboxed=False)
class ConfigureWorkflow:
    """A Configure workflow for setup MAAS Agent workers"""

    @workflow.run
    async def run(self, input: ConfigureInput) -> None:
        # Check configuration and spawn required child workflows
        # as an example we add VLAN workerts:
        return await workflow.execute_child_workflow(
            workflow="AddWorker",
            task_queue=input.system_id,
            arg={"TaskQueue": "vlan0", "Workflows": ["CheckIP"]},
        )
