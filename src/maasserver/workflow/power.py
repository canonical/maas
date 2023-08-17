from dataclasses import dataclass
from enum import Enum
from typing import Any

from temporalio import workflow


class PowerAction(Enum):
    ON = 1
    OFF = 2
    CYCLE = 3
    QUERY = 4


@dataclass
class PowerParam:
    system_id: str
    action: PowerAction
    queue: str
    params: dict[str, Any]


@dataclass
class PowerNParam:
    params: list[PowerParam]


@workflow.defn(name="PowerNWorkflow", sandboxed=False)
class PowerNWorkflow:
    @workflow.run
    async def run(self, params: PowerNParam):
        for param in params.params:
            workflow = ""
            match param.action:
                case PowerAction.ON:
                    workflow = "power_on"
                case PowerAction.OFF:
                    workflow = "power_off"
                case PowerAction.CYCLE:
                    workflow = "power_cycle"
                case PowerAction.QUERY:
                    workflow = "power_query"

            if workflow:
                await workflow.execute_child_workflow(
                    workflow,
                    param,
                    id=f"power-{param.system_id}",
                    task_queue=param.queue,
                )
