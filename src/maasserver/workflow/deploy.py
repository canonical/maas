from dataclasses import dataclass

from temporalio import workflow


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
                id=f"deploy-{param.system_id}",
                task_queue=param.queue,
            )
