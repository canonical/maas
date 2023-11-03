from dataclasses import dataclass
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

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
    task_queue: str
    driver_type: str
    driver_opts: dict[str, Any]


@dataclass
class PowerManyParam:
    params: list[PowerParam]


@dataclass
class PowerResult:
    status: str


@workflow.defn(name="power-many", sandboxed=False)
class PowerManyWorkflow:
    @workflow.run
    async def run(self, params: PowerManyParam) -> list[PowerResult]:
        results = []
        for param in params.params:
            workflow_name = ""
            if param.action in POWER_ACTION_WORKFLOWS:
                workflow_name = param.action

            if workflow_name:
                result = await workflow.execute_child_workflow(
                    workflow_name,
                    param,
                    task_queue=param.task_queue,
                    retry_policy=RetryPolicy(maximum_attempts=5),
                )
                if result:
                    results.append(result)
            else:
                raise InvalidPowerActionException(
                    f"Invalid power action: {param.action}"
                )

        return results
