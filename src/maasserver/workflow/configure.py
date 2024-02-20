from dataclasses import dataclass
from datetime import timedelta
from typing import Any

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
from maasserver.workflow.activity import ActivityBase

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
                return [vlan_id[0] for vlan_id in result]
            return []

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
            return [
                {
                    "subnet": str(endpoint[0]),
                    "endpoint": _format_endpoint(str(endpoint[1])),
                }
                for endpoint in endpoints
            ]


@dataclass
class ConfigureAgentInput:
    system_id: str
    task_queue: str


def _format_endpoint(ip: str) -> str:
    addr = IPAddress(ip)
    if addr.version == 4:
        return f"http://{ip}:5240/MAAS/"
    return f"http://[{ip}]:5240/MAAS/"


@workflow.defn(name="configure-agent", sandboxed=False)
class ConfigureAgentWorkflow:
    """A ConfigureAgent workflow to setup MAAS Agent"""

    @workflow.run
    async def run(self, input: ConfigureAgentInput) -> None:
        endpoints = await workflow.execute_activity(
            "get-region-controller-endpoints",
            start_to_close_timeout=DEFAULT_CONFIGURE_ACTIVITY_TIMEOUT,
            retry_policy=DEFAULT_CONFIGURE_RETRY_POLICY,
        )

        vlan_ids = await workflow.execute_activity(
            "get-rack-controller-vlans",
            GetRackControllerVLANsInput(input.system_id),
            start_to_close_timeout=DEFAULT_CONFIGURE_ACTIVITY_TIMEOUT,
            retry_policy=DEFAULT_CONFIGURE_RETRY_POLICY,
        )

        params = []
        # add worker for {systemID}@agent
        # this is a unicast task queue picked only by the agent running on
        # machine identified by systemID
        params.append(
            {
                "task_queue": f"{input.system_id}@agent",
                "workflows": [
                    "check-ip",
                ],
                "activities": [
                    "power-query",
                    "power-cycle",
                    "power-on",
                    "power-off",
                ],
            },
        )

        # for each VLAN add anycast workers agent:vlan-{vlan_id}
        # this is an anycast task queue polled by multiple agents
        # that can reach a certain VLAN
        #
        # If you need to extend workflows/activities that should be
        # registered, ensure they are allowed by the worker pool (MAAS Agent)
        params.extend(
            [
                {
                    "task_queue": f"agent:vlan-{vlan_id}",
                    "workflows": [
                        "check-ip",
                    ],
                    "activities": [
                        "power-query",
                        "power-cycle",
                        "power-on",
                        "power-off",
                    ],
                }
                for vlan_id in vlan_ids
            ],
        )

        await workflow.execute_activity(
            "configure-worker-pool",
            params,
            task_queue=input.task_queue,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # TODO dynamically determine whether the agent needs to run the proxy
        await workflow.execute_activity(
            "configure-http-proxy",
            {
                "endpoints": endpoints,
            },
            task_queue=input.task_queue,
            start_to_close_timeout=timedelta(seconds=30),
        )
