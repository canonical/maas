# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional

from netaddr import IPAddress
from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy

from maascommon.enums.node import NodeTypeEnum
from maascommon.workflows.configure import (
    CONFIGURE_AGENT_WORKFLOW_NAME,
    CONFIGURE_DHCP_SERVICE_WORKFLOW_NAME,
    CONFIGURE_HTTPPROXY_SERVICE_WORKFLOW_NAME,
    CONFIGURE_POWER_SERVICE_WORKFLOW_NAME,
    CONFIGURE_RESOLVER_SERVICE_WORKFLOW_NAME,
    ConfigureAgentParam,
    ConfigureDHCPServiceParam,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.db.repositories.subnets import SubnetClauseFactory
from maasservicelayer.db.repositories.vlans import VlansClauseFactory
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)

DEFAULT_CONFIGURE_ACTIVITY_TIMEOUT = timedelta(seconds=10)
DEFAULT_CONFIGURE_RETRY_POLICY = RetryPolicy(
    backoff_coefficient=2.0,
    maximum_attempts=5,
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=2),
)

# Activities names
GET_RACK_CONTROLLER_VLANS_ACTIVITY_NAME = "get-rack-controller-vlans"
GET_REGION_CONTROLLER_ENDPOINTS_ACTIVITY_NAME = (
    "get-region-controller-endpoints"
)
GET_RESOLVER_CONFIG_ACTIVITY_NAME = "get-resolver-config"


# Activities parameters
@dataclass
class GetRackControllerVLANsInput:
    system_id: str


@dataclass
class GetResolverConfigInput:
    system_id: str
    use_bind: bool


@dataclass
class GetRackControllerVLANsResult:
    vlans: List[int]


@dataclass
class GetRegionControllerEndpointsResult:
    endpoints: List[str]


@dataclass
class GetResolverConfigResult:
    enabled: bool
    bind_ips: Optional[list[str]] = None
    authoritative_ips: Optional[list[str]] = None


class ConfigureAgentActivity(ActivityBase):
    @activity_defn_with_context(name=GET_RACK_CONTROLLER_VLANS_ACTIVITY_NAME)
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

    @activity_defn_with_context(
        name=GET_REGION_CONTROLLER_ENDPOINTS_ACTIVITY_NAME
    )
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

    @activity_defn_with_context(name=GET_RESOLVER_CONFIG_ACTIVITY_NAME)
    async def get_resolver_config(
        self, param: GetResolverConfigInput
    ) -> GetResolverConfigResult:
        async with self.start_transaction() as services:
            agent_node = await services.nodes.get_one(
                query=QuerySpec(
                    where=NodeClauseFactory.with_system_id(param.system_id),
                )
            )

            # TODO remove BIND check once recursive resolver is fully functional
            # and BIND can be removed from the rack controller
            if (
                agent_node.node_type == NodeTypeEnum.REGION_CONTROLLER
                or agent_node.node_type
                == NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                or param.use_bind
            ):
                return GetResolverConfigResult(
                    enabled=False,
                )

            dns_enabled_subnets = await services.subnets.get_many(
                query=QuerySpec(
                    where=SubnetClauseFactory.with_allow_dns(True),
                )
            )

            dns_enabled_subnet_ids = [
                subnet.id for subnet in dns_enabled_subnets
            ]

            agent_ips = await services.staticipaddress.get_for_nodes(
                query=QuerySpec(
                    where=StaticIPAddressClauseFactory.and_clauses(
                        [
                            StaticIPAddressClauseFactory.with_node_system_id(
                                param.system_id
                            ),
                            StaticIPAddressClauseFactory.with_subnet_id_in(
                                dns_enabled_subnet_ids
                            ),
                        ]
                    ),
                )
            )

            region_ips = await services.staticipaddress.get_for_nodes(
                query=QuerySpec(
                    where=StaticIPAddressClauseFactory.and_clauses(
                        [
                            StaticIPAddressClauseFactory.or_clauses(
                                [
                                    StaticIPAddressClauseFactory.with_node_type(
                                        NodeTypeEnum.REGION_CONTROLLER
                                    ),
                                    StaticIPAddressClauseFactory.with_node_type(
                                        NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                                    ),
                                ]
                            ),
                            StaticIPAddressClauseFactory.with_subnet_id_in(
                                dns_enabled_subnet_ids
                            ),
                        ]
                    ),
                ),
            )

            return GetResolverConfigResult(
                enabled=True,
                bind_ips=list(set(str(sip.ip) for sip in agent_ips)),
                authoritative_ips=list(set(str(sip.ip) for sip in region_ips)),
            )


def _format_endpoint(ip: str) -> str:
    addr = IPAddress(ip)
    if addr.version == 4:
        return f"http://{ip}:5240/MAAS/"
    return f"http://[{ip}]:5240/MAAS/"


# NOTE: Once Region can detect that Agent was reconnected or restarted
# via Temporal server API, we should no longer need this workflow
# and Region should execute per-service workflow for configuration.
@workflow.defn(name=CONFIGURE_AGENT_WORKFLOW_NAME, sandboxed=False)
class ConfigureAgentWorkflow:
    """A ConfigureAgent workflow to setup MAAS Agent"""

    @workflow_run_with_context
    async def run(self, param: ConfigureAgentParam) -> None:
        # Agent registers workflows for configuring it's services
        # during Temporal worker pool initialization using WithConfigurator.
        # Make sure that used workflow names are in sync with the Agent.
        await workflow.execute_child_workflow(
            CONFIGURE_POWER_SERVICE_WORKFLOW_NAME,
            param.system_id,
            id=f"configure-power-service:{param.system_id}",
            task_queue=f"{param.system_id}@agent:main",
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        await workflow.execute_child_workflow(
            CONFIGURE_HTTPPROXY_SERVICE_WORKFLOW_NAME,
            param.system_id,
            id=f"configure-httpproxy-service:{param.system_id}",
            task_queue=f"{param.system_id}@agent:main",
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        await workflow.execute_child_workflow(
            CONFIGURE_DHCP_SERVICE_WORKFLOW_NAME,
            ConfigureDHCPServiceParam(enabled=True),
            id=f"configure-dhcp-service:{param.system_id}",
            task_queue=f"{param.system_id}@agent:main",
            retry_policy=RetryPolicy(maximum_attempts=1),
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )

        await workflow.execute_child_workflow(
            CONFIGURE_RESOLVER_SERVICE_WORKFLOW_NAME,
            param.system_id,
            task_queue=f"{param.system_id}@agent:main",
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
