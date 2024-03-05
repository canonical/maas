from dataclasses import dataclass
from datetime import timedelta
from typing import Any, List

from netaddr import IPAddress
from sqlalchemy import or_, select
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from maasapiserver.common.db.tables import (
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
    SubnetTable,
    VlanTable,
)
from maasserver.enum import NODE_TYPE
from maastemporalworker.workflow.activity import ActivityBase

DEFAULT_CONFIGURE_ACTIVITY_TIMEOUT = timedelta(seconds=10)
DEFAULT_CONFIGURE_RETRY_POLICY = RetryPolicy(
    backoff_coefficient=2.0,
    maximum_attempts=5,
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=2),
)


@dataclass
class GetRackControllerVLANsInput:
    system_id: str


@dataclass
class GetRackControllerVLANsResult:
    vlans: List[int]


@dataclass
class GetRegionControllerEndpointsResult:
    endpoints: List[str]


class ConfigureAgentActivity(ActivityBase):
    @activity.defn(name="get-rack-controller-vlans")
    async def get_rack_controller_vlans(
        self, input: GetRackControllerVLANsInput
    ):
        async with self.start_transaction() as tx:
            stmt = (
                select(
                    VlanTable.c.id,
                )
                .select_from(NodeTable)
                .join(
                    NodeConfigTable,
                    NodeTable.c.current_config_id == NodeConfigTable.c.id,
                )
                .join(
                    InterfaceTable,
                    NodeConfigTable.c.id == InterfaceTable.c.node_config_id,
                    isouter=True,
                )
                .join(
                    InterfaceIPAddressTable,
                    InterfaceTable.c.id
                    == InterfaceIPAddressTable.c.interface_id,
                    isouter=True,
                )
                .join(
                    StaticIPAddressTable,
                    InterfaceIPAddressTable.c.staticipaddress_id
                    == StaticIPAddressTable.c.id,
                    isouter=True,
                )
                .join(
                    SubnetTable,
                    SubnetTable.c.id == StaticIPAddressTable.c.subnet_id,
                    isouter=True,
                )
                .join(
                    VlanTable,
                    or_(
                        VlanTable.c.id == SubnetTable.c.vlan_id,
                        VlanTable.c.id == InterfaceTable.c.vlan_id,
                    ),
                )
                .filter(
                    NodeTable.c.system_id == input.system_id,
                    or_(
                        NodeTable.c.node_type == NODE_TYPE.RACK_CONTROLLER,
                        NodeTable.c.node_type
                        == NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                    ),
                )
            )
            result = (await tx.execute(stmt)).all()
            if result:
                return GetRackControllerVLANsResult(
                    [vlan_id[0] for vlan_id in result]
                )
            return GetRackControllerVLANsResult([])

    @activity.defn(name="get-region-controller-endpoints")
    async def get_region_controller_endpoints(self) -> dict[str, Any]:
        async with self.start_transaction() as tx:
            stmt = (
                select(
                    SubnetTable.c.cidr,
                    StaticIPAddressTable.c.ip,
                )
                .select_from(NodeTable)
                .join(
                    NodeConfigTable,
                    NodeTable.c.current_config_id == NodeConfigTable.c.id,
                )
                .join(
                    InterfaceTable,
                    NodeConfigTable.c.id == InterfaceTable.c.node_config_id,
                )
                .join(
                    InterfaceIPAddressTable,
                    InterfaceTable.c.id
                    == InterfaceIPAddressTable.c.interface_id,
                )
                .join(
                    StaticIPAddressTable,
                    InterfaceIPAddressTable.c.staticipaddress_id
                    == StaticIPAddressTable.c.id,
                )
                .join(
                    SubnetTable,
                    SubnetTable.c.id == StaticIPAddressTable.c.subnet_id,
                )
                .filter(
                    or_(
                        NodeTable.c.node_type == NODE_TYPE.REGION_CONTROLLER,
                        NodeTable.c.node_type
                        == NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                    ),
                )
            )
            endpoints = (await tx.execute(stmt)).all()
            return GetRegionControllerEndpointsResult(
                [_format_endpoint(str(endpoint[1])) for endpoint in endpoints]
            )


@dataclass
class ConfigureAgentParam:
    system_id: str


def _format_endpoint(ip: str) -> str:
    addr = IPAddress(ip)
    if addr.version == 4:
        return f"http://{ip}:5240/MAAS/"
    return f"http://[{ip}]:5240/MAAS/"


# NOTE: Once Region can detect that Agent was reconnected or restarted
# via Temporal server API, we should no longer need this workflow
# and Region should execute per-service workflow for configuration.
@workflow.defn(name="configure-agent", sandboxed=False)
class ConfigureAgentWorkflow:
    """A ConfigureAgent workflow to setup MAAS Agent"""

    @workflow.run
    async def run(self, param: ConfigureAgentParam) -> None:
        # Agent registers workflows for configuring it's services
        # during Temporal worker pool initialization using WithConfigurator.
        # Make sure that used workflow names are in sync with the Agent.
        await workflow.execute_child_workflow(
            "configure-power-service",
            param.system_id,
            id=f"configure-power-service:{param.system_id}",
            task_queue=f"{param.system_id}@agent:main",
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        await workflow.execute_child_workflow(
            "configure-httpproxy-service",
            param.system_id,
            id=f"configure-httpproxy-service:{param.system_id}",
            task_queue=f"{param.system_id}@agent:main",
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
