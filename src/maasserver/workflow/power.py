from dataclasses import dataclass
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

POWER_ACTION_WORKFLOWS = (
    "power-on",
    "power-off",
    "power-cycle",
    "power-query",
)


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
            if param.action not in POWER_ACTION_WORKFLOWS:
                workflow.logger.warn(
                    f"Invalid power action {param.action} for machine {param.system_id}"
                )
                continue

            result = await workflow.execute_child_workflow(
                param.action,
                param,
                task_queue=param.task_queue,
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            if result:
                results.append(result)

        return results
