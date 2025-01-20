#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
import uuid

from temporalio import workflow
from temporalio.common import RetryPolicy

from maascommon.enums.power import PowerState
from maascommon.workflows.power import (
    POWER_CYCLE_WORKFLOW_NAME,
    POWER_MANY_WORKFLOW_NAME,
    POWER_OFF_WORKFLOW_NAME,
    POWER_ON_WORKFLOW_NAME,
    POWER_QUERY_WORKFLOW_NAME,
    PowerAction,
    PowerCycleParam,
    PowerManyParam,
    PowerOffParam,
    PowerOnParam,
    PowerQueryParam,
)
from maasserver.workflow.worker.worker import REGION_TASK_QUEUE
from maasservicelayer.models.nodes import NodeBuilder
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import activity_defn_with_context

# Maximum power activity duration (to cope with broken BMCs)
POWER_ACTION_ACTIVITY_TIMEOUT = timedelta(minutes=5)

# Activities names
POWER_ON_ACTIVITY_NAME = "power-on"
POWER_OFF_ACTIVITY_NAME = "power-off"
POWER_CYCLE_ACTIVITY_NAME = "power-cycle"
POWER_QUERY_ACTIVITY_NAME = "power-query"
SET_POWER_STATE_ACTIVITY_NAME = "set-power-state"


# Activities parameters
@dataclass
class PowerOnResult:
    """
    Result returned by PowerOn workflow
    """

    state: str


@dataclass
class PowerOffResult:
    """
    Result returned by PowerOff workflow
    """

    state: str


@dataclass
class PowerCycleResult:
    """
    Result returned by PowerCycle workflow
    """

    state: str


@dataclass
class PowerQueryResult:
    """
    Result returned by PowerQuery workflow
    """

    state: str


@dataclass
class SetPowerStateParam:
    """
    Parameters to set the power state of a machine
    """

    system_id: str
    state: PowerState
    timestamp: Optional[datetime] = None


class PowerActivity(ActivityBase):

    @activity_defn_with_context(name=SET_POWER_STATE_ACTIVITY_NAME)
    async def set_power_state(self, params: SetPowerStateParam) -> None:
        async with self.start_transaction() as services:
            builder = NodeBuilder(
                power_state=params.state,
                power_state_updated=(
                    params.timestamp if params.timestamp else utcnow()
                ),
            )

            await services.nodes.update_by_system_id(params.system_id, builder)


@workflow.defn(name=POWER_ON_WORKFLOW_NAME, sandboxed=False)
class PowerOnWorkflow:
    """
    PowerOnWorkflow is executed by the Region Controller itself.
    """

    # TODO: we can use structlogs from 3.7 once the power workflows are registered only on the maastemporalworker
    # @workflow_run_with_context
    @workflow.run
    async def run(self, param: PowerOnParam) -> PowerOnResult:
        result = await workflow.execute_activity(
            POWER_ON_ACTIVITY_NAME,
            {
                "driver_type": param.driver_type,
                "driver_opts": param.driver_opts,
            },
            task_queue=param.task_queue,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=POWER_ACTION_ACTIVITY_TIMEOUT,
        )

        return result


@workflow.defn(name=POWER_OFF_WORKFLOW_NAME, sandboxed=False)
class PowerOffWorkflow:
    """
    PowerOffWorkflow is executed by the Region Controller itself.
    """

    # TODO: we can use structlogs from 3.7 once the power workflows are registered only on the maastemporalworker
    # @workflow_run_with_context
    @workflow.run
    async def run(self, param: PowerOffParam) -> PowerOffResult:
        result = await workflow.execute_activity(
            POWER_OFF_ACTIVITY_NAME,
            {
                "driver_type": param.driver_type,
                "driver_opts": param.driver_opts,
            },
            task_queue=param.task_queue,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=POWER_ACTION_ACTIVITY_TIMEOUT,
        )

        return result


@workflow.defn(name=POWER_CYCLE_WORKFLOW_NAME, sandboxed=False)
class PowerCycleWorkflow:
    """
    PowerCycleWorkflow is executed by the Region Controller itself.
    """

    # TODO: we can use structlogs from 3.7 once the power workflows are registered only on the maastemporalworker
    # @workflow_run_with_context
    @workflow.run
    async def run(self, param: PowerCycleParam) -> PowerCycleResult:
        result = await workflow.execute_activity(
            POWER_CYCLE_ACTIVITY_NAME,
            {
                "driver_type": param.driver_type,
                "driver_opts": param.driver_opts,
            },
            task_queue=param.task_queue,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=POWER_ACTION_ACTIVITY_TIMEOUT,
        )

        return result


@workflow.defn(name=POWER_QUERY_WORKFLOW_NAME, sandboxed=False)
class PowerQueryWorkflow:
    """
    PowerQueryWorkflow is executed by the Region Controller itself.
    """

    # TODO: we can use structlogs from 3.7 once the power workflows are registered only on the maastemporalworker
    # @workflow_run_with_context
    @workflow.run
    async def run(self, param: PowerQueryParam) -> PowerQueryResult:
        result = await workflow.execute_activity(
            POWER_QUERY_ACTIVITY_NAME,
            {
                "driver_type": param.driver_type,
                "driver_opts": param.driver_opts,
            },
            task_queue=param.task_queue,
            retry_policy=RetryPolicy(maximum_attempts=3),
            start_to_close_timeout=POWER_ACTION_ACTIVITY_TIMEOUT,
        )
        return result


@workflow.defn(name=POWER_MANY_WORKFLOW_NAME, sandboxed=False)
class PowerManyWorkflow:
    """
    PowerManyWorkflow is executed by the Region Controller itself.
    It spawns requested child workflows but doesn't collect results.
    """

    # TODO: we can use structlogs from 3.7 once the power workflows are registered only on the maastemporalworker
    # @workflow_run_with_context
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
