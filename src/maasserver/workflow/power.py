from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any, Optional
import uuid

from temporalio import workflow
from temporalio.common import RetryPolicy

from maasserver.workflow.worker.worker import REGION_TASK_QUEUE

# Maximum power activity duration (to cope with broken BMCs)
POWER_ACTION_ACTIVITY_TIMEOUT = timedelta(minutes=5)


# XXX: Once Python 3.11 switch to StrEnum
class PowerAction(Enum):
    POWER_ON = "power-on"
    POWER_OFF = "power-off"
    POWER_CYCLE = "power-cycle"
    POWER_QUERY = "power-query"


@dataclass
class PowerParam:
    system_id: str

    # XXX: should be removed, once we can fetch everything by system_id
    # inside workflow itself and pass to the underlying PowerOn activity.
    driver_type: str
    driver_opts: dict[str, Any]
    task_queue: str


@dataclass
class PowerOnParam(PowerParam):
    """
    Parameters required by the PowerOn workflow
    """

    pass


@dataclass
class PowerOnResult:
    """
    Result returned by PowerOn workflow
    """

    state: str


@dataclass
class PowerOffParam(PowerParam):
    """
    Parameters required by the PowerOff workflow
    """

    pass


@dataclass
class PowerOffResult:
    """
    Result returned by PowerOff workflow
    """

    state: str


@dataclass
class PowerCycleParam(PowerParam):
    """
    Parameters required by the PowerCycle workflow
    """

    pass


@dataclass
class PowerCycleResult:
    """
    Result returned by PowerCycle workflow
    """

    state: str


@dataclass
class PowerQueryParam(PowerParam):
    """

    Parameters required by the PowerQuery workflow
    """

    pass


@dataclass
class PowerQueryResult:
    """
    Result returned by PowerQuery workflow
    """

    state: str


@workflow.defn(name="power-on", sandboxed=False)
class PowerOnWorkflow:
    """
    PowerOnWorkflow is executed by the Region Controller itself.
    """

    @workflow.run
    async def run(self, param: PowerOnParam) -> PowerOnResult:
        result = await workflow.execute_activity(
            "power-on",
            {
                "driver_type": param.driver_type,
                "driver_opts": param.driver_opts,
            },
            task_queue=param.task_queue,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=POWER_ACTION_ACTIVITY_TIMEOUT,
        )

        return result


@workflow.defn(name="power-off", sandboxed=False)
class PowerOffWorkflow:
    """
    PowerOffWorkflow is executed by the Region Controller itself.
    """

    @workflow.run
    async def run(self, param: PowerOffParam) -> PowerOffResult:
        result = await workflow.execute_activity(
            "power-off",
            {
                "driver_type": param.driver_type,
                "driver_opts": param.driver_opts,
            },
            task_queue=param.task_queue,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=POWER_ACTION_ACTIVITY_TIMEOUT,
        )

        return result


@workflow.defn(name="power-cycle", sandboxed=False)
class PowerCycleWorkflow:
    """
    PowerCycleWorkflow is executed by the Region Controller itself.
    """

    @workflow.run
    async def run(self, param: PowerCycleParam) -> PowerCycleResult:
        result = await workflow.execute_activity(
            "power-cycle",
            {
                "driver_type": param.driver_type,
                "driver_opts": param.driver_opts,
            },
            task_queue=param.task_queue,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=POWER_ACTION_ACTIVITY_TIMEOUT,
        )

        return result


@workflow.defn(name="power-query", sandboxed=False)
class PowerQueryWorkflow:
    """
    PowerQueryWorkflow is executed by the Region Controller itself.
    """

    @workflow.run
    async def run(self, param: PowerQueryParam) -> PowerQueryResult:
        result = await workflow.execute_activity(
            "power-query",
            {
                "driver_type": param.driver_type,
                "driver_opts": param.driver_opts,
            },
            task_queue=param.task_queue,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=POWER_ACTION_ACTIVITY_TIMEOUT,
        )
        return result


@dataclass
class PowerParam:
    # XXX: PoweParam class should be removed, once we can fetch everything by system_id
    system_id: str
    driver_type: str
    driver_opts: dict[str, Any]
    task_queue: str


@dataclass
class PowerManyParam:
    """
    Parameters required by the PowerMany workflow
    """

    action: str
    # XXX: params property should be removed, once we can fetch everything by system_id
    # change to list[str] (list of system_ids)
    params: list[PowerParam]


@workflow.defn(name="power-many", sandboxed=False)
class PowerManyWorkflow:
    """
    PowerManyWorkflow is executed by the Region Controller itself.
    It spawns requested child workflows but doesn't collect results.
    """

    @workflow.run
    async def run(self, param: PowerManyParam) -> None:
        for child in param.params:
            await workflow.start_child_workflow(
                param.action,
                child,
                id=str(uuid.uuid4()),
                task_queue=REGION_TASK_QUEUE,
                retry_policy=RetryPolicy(maximum_attempts=1),
                execution_timeout=timedelta(minutes=60),
            )


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
        return f"agent:power@vlan-{bmc_vlan.id}"

    # Check if there are any rack controllers/agents that have access to
    # the BMC by routing instead of having direct layer 2 access.
    # TODO: check that picked rack/agent has connection to Temporal
    # with_connection=True is a temporary solution that relies on RPC
    racks = machine.bmc.get_routable_usable_rack_controllers(
        with_connection=True
    )
    if racks:
        return f"{racks[0].system_id}@agent:power"

    raise UnroutablePowerWorkflowException(
        f"Error determining BMC task queue for machine {machine.system_id}"
    )


class UnknownPowerActionException(Exception):
    pass


# XXX: remove this temporary solution, once we switch to SQLAlchemy
def convert_power_action_to_power_workflow(
    power_action: str, machine: Any, extra_params: Optional[Any] = None
) -> tuple[str, Any]:
    """
    This function converts power action and power parameters into Power
    Temporal workflow with corresponding parameters.

    Power is an 'umbrella' workflow that allows execution of multiple Power
    commands at once.
    """

    match power_action:
        case PowerAction.POWER_ON.value:
            return (
                power_action,
                PowerOnParam(
                    system_id=machine.system_id,
                    task_queue=get_temporal_task_queue_for_bmc(machine),
                    driver_type=extra_params.power_type,
                    driver_opts=extra_params.power_parameters,
                ),
            )
        case PowerAction.POWER_OFF.value:
            return (
                power_action,
                PowerOffParam(
                    system_id=machine.system_id,
                    task_queue=get_temporal_task_queue_for_bmc(machine),
                    driver_type=extra_params.power_type,
                    driver_opts=extra_params.power_parameters,
                ),
            )
        case PowerAction.POWER_CYCLE.value:
            return (
                power_action,
                PowerCycleParam(
                    system_id=machine.system_id,
                    task_queue=get_temporal_task_queue_for_bmc(machine),
                    driver_type=extra_params.power_type,
                    driver_opts=extra_params.power_parameters,
                ),
            )
        case PowerAction.POWER_QUERY.value:
            return (
                power_action,
                PowerQueryParam(
                    system_id=machine.system_id,
                    task_queue=get_temporal_task_queue_for_bmc(machine),
                    driver_type=extra_params.power_type,
                    driver_opts=extra_params.power_parameters,
                ),
            )
        case _:
            raise UnknownPowerActionException()
