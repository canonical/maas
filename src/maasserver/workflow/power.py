from dataclasses import dataclass
from typing import Any

from temporalio import workflow

POWER_ACTION_WORKFLOWS = (
    "power_on",
    "power_off",
    "power_cycle",
    "power_query",
)


class InvalidPowerActionException(Exception):
    pass


@dataclass
class PowerParam:
    system_id: str
    action: str
    queue: str
    power_type: str
    params: dict[str, Any]


@dataclass
class PowerNParam:
    params: list[PowerParam]


@dataclass
class PowerResult:
    status: str


@workflow.defn(name="PowerNWorkflow", sandboxed=False)
class PowerNWorkflow:
    @workflow.run
    async def run(self, params: PowerNParam) -> list[PowerResult]:
        results = []
        info = workflow.info()
        # parent workflow_id should contain a monotonic timestamp
        # to ensure uniqueness
        timestamp = info.workflow_id.split(":")[-1]
        for param in params.params:
            workflow_name = ""
            if param.action in POWER_ACTION_WORKFLOWS:
                workflow_name = param.action

            if workflow_name:
                result = await workflow.execute_child_workflow(
                    workflow_name,
                    param,
                    id=f"power:{workflow_name}:{param.system_id}:{timestamp}",
                    task_queue=param.queue,
                )
                if result:
                    results.append(result)
            else:
                raise InvalidPowerActionException(
                    f"invalid power action: {param.action}"
                )

        return results
