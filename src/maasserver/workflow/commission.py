from dataclasses import dataclass

from temporalio import workflow


@dataclass
class CommissionParam:
    system_id: str
    queue: str


@dataclass
class CommissionNParam:
    params: list[CommissionParam]


@workflow.defn(name="CommissionNWorkflow", sandboxed=False)
class CommissionNWorkflow:
    @workflow.run
    async def run(self, params: CommissionNParam) -> None:
        for param in params.params:
            await workflow.execute_child_workflow(
                "commission",
                param,
                id=f"commission-{param.system_id}",
                task_queue=param.queue,
            )
