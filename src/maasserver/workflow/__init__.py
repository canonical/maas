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
from maasserver.workflow.power import (
    PowerAction,
    PowerNParam,
    PowerNWorkflow,
    PowerParam,
)

MACHINE_ACTION_WORKFLOWS = (
    "commission",
    "deploy",
    "power_on",
    "power_off",
    "power_query",
    "power_cycle",
)


def get_temporal_queue_for_machine(machine):
    vlan_id = None
    if machine.boot_interface:
        vlan_id = machine.boot_interface.vlan.id
        return f"vlan-{vlan_id}"


def to_temporal_params(name, objects, extra_params):
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
                            action=PowerAction.ON,
                            queue=get_temporal_queue_for_machine(o),
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
                            action=PowerAction.OFF,
                            queue=get_temporal_queue_for_machine(o),
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
                            action=PowerAction.QUERY,
                            queue=get_temporal_queue_for_machine(o),
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
                            action=PowerAction.CYCLE,
                            queue=get_temporal_queue_for_machine(o),
                        )
                        for o in objects
                    ]
                ),
            )


__all__ = [
    "CommissionParam",
    "CommissionNParam",
    "CommissionNWorkflow",
    "DeployParam",
    "DeployNParam",
    "DeployNWorkflow",
    "MACHINE_ACTION_WORKFLOWS",
    "PowerAction",
    "PowerParam",
    "PowerNParam",
    "PowerNWorkflow",
]
