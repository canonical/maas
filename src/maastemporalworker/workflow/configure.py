# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import timedelta
from typing import List

from netaddr import IPAddress
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.db.repositories.vlans import VlansClauseFactory
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
    ) -> GetRackControllerVLANsResult:
        async with self.start_transaction() as services:
            result = await services.vlans.get_node_vlans(
                query=QuerySpec(
                    where=VlansClauseFactory.and_clauses(
                        [
                            VlansClauseFactory.with_system_id(input.system_id),
                            VlansClauseFactory.or_clauses(
                                [
                                    VlansClauseFactory.with_node_type(
                                        NodeTypeEnum.RACK_CONTROLLER
                                    ),
                                    VlansClauseFactory.with_node_type(
                                        NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                                    ),
                                ]
                            ),
                        ]
                    )
                )
            )
            if result:
                return GetRackControllerVLANsResult(
                    [vlan.id for vlan in result]
                )
            return GetRackControllerVLANsResult([])

    @activity.defn(name="get-region-controller-endpoints")
    async def get_region_controller_endpoints(
        self,
    ) -> GetRegionControllerEndpointsResult:
        async with self.start_transaction() as services:
            result = await services.staticipaddress.get_for_nodes(
                query=QuerySpec(
                    where=StaticIPAddressClauseFactory.or_clauses(
                        [
                            StaticIPAddressClauseFactory.with_node_type(
                                NodeTypeEnum.REGION_CONTROLLER
                            ),
                            StaticIPAddressClauseFactory.with_node_type(
                                NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                            ),
                        ]
                    )
                )
            )
            return GetRegionControllerEndpointsResult(
                [_format_endpoint(str(ipaddress.ip)) for ipaddress in result]
            )


@dataclass
class ConfigureAgentParam:
    system_id: str


@dataclass
class ConfigureDHCPServiceParam:
    enabled: bool


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

        await workflow.execute_child_workflow(
            "configure-dhcp-service",
            ConfigureDHCPServiceParam(enabled=True),
            id=f"configure-dhcp-service:{param.system_id}",
            task_queue=f"{param.system_id}@agent:main",
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
