from dataclasses import dataclass
from typing import Any, Optional

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
    task_queue: str
    driver_type: str
    driver_opts: dict[str, Any]


@dataclass
class PowerManyParam:
    action: str
    params: list[PowerParam]


@dataclass
class PowerResult:
    status: str


@workflow.defn(name="power-many", sandboxed=False)
class PowerManyWorkflow:
    @workflow.run
    async def run(self, params: PowerManyParam) -> list[PowerResult]:
        results = []
        if params.action not in POWER_ACTION_WORKFLOWS:
            workflow.logger.warn(f"Invalid power action {params.action}")

            return results

        for param in params.params:
            result = await workflow.execute_child_workflow(
                params.action,
                param,
                task_queue=param.task_queue,
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            if result:
                results.append(result)

        return results


class UnroutablePowerWorkflowException(Exception):
    pass


def get_temporal_task_queue_for_bmc(machine: Any) -> str:
    bmc_vlan = None
    try:
        bmc_vlan = machine.bmc.ip_address.subnet.vlan
    except AttributeError:
        pass

    # Check if there are any rack controllers that are connected to this VLAN.
    # If such rack controllers exist, use vlan specific task queue.
    if bmc_vlan and bmc_vlan.connected_rack_controllers():
        return f"agent:vlan-{bmc_vlan.id}"

    # Check if there are any rack controllers/agents that have access to
    # the BMC by routing instead of having direct layer 2 access.
    # TODO: check that picked rack/agent has connection to Temporal
    # with_connection=True is a temporary solution that relies on RPC
    racks = machine.bmc.get_routable_usable_rack_controllers(
        with_connection=True
    )
    if racks:
        return f"{racks[0].system_id}@agent"

    raise UnroutablePowerWorkflowException(
        f"Error determining BMC task queue for machine {machine.system_id}"
    )


class UnknownPowerActionException(Exception):
    pass


def convert_power_action_to_power_workflow(
    power_action: str, machine: Any, extra_params: Optional[Any] = None
) -> tuple[str, Any]:
    """
    This function converts power action and power parameters into PowerMany
    Temporal workflow with corresponding parameters.

    PowerMany is an 'umbrella' workflow that allows execution of multiple Power
    commands at once.
    """
    match power_action:
        case "power_on":
            return (
                "power-many",
                PowerManyParam(
                    action="power-on",
                    params=[
                        PowerParam(
                            system_id=machine.system_id,
                            task_queue=get_temporal_task_queue_for_bmc(
                                machine
                            ),
                            driver_type=extra_params.power_type,
                            driver_opts=extra_params.power_parameters,
                        )
                    ],
                ),
            )
        case "power_off":
            return (
                "power-many",
                PowerManyParam(
                    action="power-off",
                    params=[
                        PowerParam(
                            system_id=machine.system_id,
                            task_queue=get_temporal_task_queue_for_bmc(
                                machine
                            ),
                            driver_type=extra_params.power_type,
                            driver_opts=extra_params.power_parameters,
                        )
                    ],
                ),
            )
        case "power_query":
            return (
                "power-many",
                PowerManyParam(
                    action="power-query",
                    params=[
                        PowerParam(
                            system_id=machine.system_id,
                            task_queue=get_temporal_task_queue_for_bmc(
                                machine
                            ),
                            driver_type=extra_params.power_type,
                            driver_opts=extra_params.power_parameters,
                        )
                    ],
                ),
            )
        case "power_cycle":
            return (
                "power-many",
                PowerManyParam(
                    action="power-cycle",
                    params=[
                        PowerParam(
                            system_id=machine.system_id,
                            task_queue=get_temporal_task_queue_for_bmc(
                                machine
                            ),
                            driver_type=extra_params.power_type,
                            driver_opts=extra_params.power_parameters,
                        )
                    ],
                ),
            )
        case _:
            raise UnknownPowerActionException()
