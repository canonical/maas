# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from functools import wraps
from typing import Any, Optional

from twisted.internet.defer import Deferred, succeed

from maasserver.eventloop import services
from maasserver.regiondservices.temporal_worker import TemporalWorkerService
from maasserver.workflow.commission import (
    CommissionNParam,
    CommissionNWorkflow,
    CommissionParam,
)
from maasserver.workflow.deploy import (
    DeployNParam,
    DeployNWorkflow,
    DeployParam,
)
from maasserver.workflow.power import PowerNParam, PowerNWorkflow, PowerParam
from maasserver.workflow.worker import get_client_async, REGION_TASK_QUEUE
from provisioningserver.utils.twisted import asynchronous

MACHINE_ACTION_WORKFLOWS = (
    "power_on",
    "power_off",
    "power_query",
    "power_cycle",
)


class UnroutableWorkflowException(Exception):
    pass


def get_temporal_queue_for_machine(
    machine: Any, for_power: Optional[bool] = False
) -> str:
    vlan_id = None
    if (
        not for_power
        and machine.boot_interface
        and machine.boot_interface.vlan
    ):
        vlan_id = machine.boot_interface.vlan.id
        return f"vlan-{vlan_id}"
    else:
        if machine.bmc:
            racks = machine.bmc.get_usable_rack_controllers(
                with_connection=False
            )
            if racks:
                return f"agent:{racks[0].system_id}"
    raise UnroutableWorkflowException(
        f"no suitable task queue for machine {machine.system_id}"
    )


def to_temporal_params(
    name: str, objects: list[Any], extra_params: Optional[Any] = None
) -> tuple[str, Any]:
    match name:
        case "commission":
            return (
                "CommissionNWorkflow",
                CommissionNParam(
                    params=[
                        CommissionParam(
                            system_id=o.system_id,
                            queue=get_temporal_queue_for_machine(o),
                        )
                        for o in objects
                    ]
                ),
            )
        case "deploy":
            return (
                "DeployNWorkflow",
                DeployNParam(
                    params=[
                        DeployParam(
                            system_id=o.system_id,
                            queue=get_temporal_queue_for_machine(o),
                        )
                        for o in objects
                    ]
                ),
            )
        case "power_on":
            return (
                "PowerNWorkflow",
                PowerNParam(
                    params=[
                        PowerParam(
                            system_id=o.system_id,
                            action=name,
                            queue=get_temporal_queue_for_machine(o),
                            power_type=extra_params.power_type,
                            params=extra_params.power_parameters,
                        )
                        for o in objects
                    ]
                ),
            )
        case "power_off":
            return (
                "PowerNWorkflow",
                PowerNParam(
                    params=[
                        PowerParam(
                            system_id=o.system_id,
                            action=name,
                            queue=get_temporal_queue_for_machine(o),
                            power_type=extra_params.power_type,
                            params=extra_params.power_parameters,
                        )
                        for o in objects
                    ]
                ),
            )
        case "power_query":
            return (
                "PowerNWorkflow",
                PowerNParam(
                    params=[
                        PowerParam(
                            system_id=o.system_id,
                            action=name,
                            queue=get_temporal_queue_for_machine(o),
                            power_type=extra_params.power_type,
                            params=extra_params.power_parameters,
                        )
                        for o in objects
                    ]
                ),
            )
        case "power_cycle":
            return (
                "PowerNWorkflow",
                PowerNParam(
                    params=[
                        PowerParam(
                            system_id=o.system_id,
                            action=name,
                            queue=get_temporal_queue_for_machine(o),
                            power_type=extra_params.power_type,
                            params=extra_params.power_parameters,
                        )
                        for o in objects
                    ]
                ),
            )


def run_in_temporal_eventloop(fn, *args, **kwargs):
    temporal_worker = TemporalWorkerService(
        services.getServiceNamed("temporal-worker")
    )
    run = fn(*args, **kwargs)
    if asyncio.iscoroutine(run):
        return temporal_worker._loop.create_task(run)
    return temporal_worker._loop.create_task(asyncio.ensure_future(run))


@asynchronous(timeout=60)
def temporal_wrapper(func):
    """
    This decorator ensures Temporal code is always executed
    with an asyncio eventloop.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            run = func(*args, **kwargs)
            if asyncio.iscoroutine(run):
                task = loop.create_task(run)
            else:
                task = loop.create_task(asyncio.ensure_future(run))
            return Deferred.fromFuture(task)
        except RuntimeError:
            try:
                task = run_in_temporal_eventloop(func, *args, **kwargs)
                return Deferred.fromFuture(task)
            except KeyError:  # in worker proc
                asyncio.run(func(*args, **kwargs))
                return succeed()

    return wrapper


@temporal_wrapper
async def execute_workflow(
    workflow_name: str,
    workflow_id: str,
    params: Optional[Any] = None,
    task_queue: Optional[str] = REGION_TASK_QUEUE,
) -> Optional[Any]:
    temporal_client = await get_client_async()
    result = await temporal_client.execute_workflow(
        workflow_name,
        params,
        id=workflow_id,
        task_queue=task_queue,
    )
    if result:
        return result


__all__ = [
    "CommissionNParam",
    "CommissionNWorkflow",
    "CommissionParam",
    "DeleteBootResourceWorkflow",
    "DeployNParam",
    "DeployNWorkflow",
    "get_temporal_queue_for_machine",
    "MACHINE_ACTION_WORKFLOWS",
    "PowerParam",
    "PowerNParam",
    "PowerNWorkflow",
    "run_in_temporal_eventloop",
    "temporal_wrapper",
    "to_temporal_params",
    "UnroutableWorkflowException",
    "ResourceDeleteParam",
    "ResourceDownloadParam",
    "SyncBootResourcesWorkflow",
]
