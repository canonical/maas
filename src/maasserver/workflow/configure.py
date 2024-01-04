from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from netaddr import IPAddress
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from maasserver.workflow.api_client import MAASAPIClient

DEFAULT_CONFIGURE_ACTIVITY_TIMEOUT = timedelta(seconds=10)
DEFAULT_CONFIGURE_RETRY_POLICY = RetryPolicy(
    backoff_coefficient=2.0,
    maximum_attempts=5,
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=2),
)


@dataclass
class GetRackControllerInput:
    system_id: str


class ConfigureWorkerPoolActivity(MAASAPIClient):
    @activity.defn(name="get-rack-controller")
    async def get_rack_controller(self, input: GetRackControllerInput):
        url = f"{self.url}/api/2.0/rackcontrollers/{input.system_id}/"
        return await self.request_async("GET", url)

    @activity.defn(name="get-region-controllers")
    async def get_region_controllers(self) -> dict[str, Any]:
        url = f"{self.url}/api/2.0/regioncontrollers/"
        return await self.request_async("GET", url)


@dataclass
class ConfigureWorkerPoolInput:
    system_id: str
    task_queue: str


def _format_endpoint(ip: str) -> str:
    addr = IPAddress(ip)
    if addr.version == 4:
        return f"http://{ip}:5240/MAAS/"
    return f"http://[{ip}]:5240/MAAS/"


@workflow.defn(name="configure-agent", sandboxed=False)
class ConfigureWorkerPoolWorkflow:
    """A ConfigureWorkerPool workflow to setup MAAS Agent workers"""

    @workflow.run
    async def run(self, input: ConfigureWorkerPoolInput) -> None:
        region_controllers = await workflow.execute_activity(
            "get-region-controllers",
            start_to_close_timeout=DEFAULT_CONFIGURE_ACTIVITY_TIMEOUT,
            retry_policy=DEFAULT_CONFIGURE_RETRY_POLICY,
        )

        rack_controller = await workflow.execute_activity(
            "get-rack-controller",
            GetRackControllerInput(input.system_id),
            start_to_close_timeout=DEFAULT_CONFIGURE_ACTIVITY_TIMEOUT,
            retry_policy=DEFAULT_CONFIGURE_RETRY_POLICY,
        )

        interface_set = rack_controller["interface_set"]
        vlan_ids = set(
            [n["vlan"]["id"] for n in interface_set if n.get("vlan")]
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
                    "power-query",
                    "power-cycle",
                    "power-on",
                    "power-off",
                ],
                "activities": [
                    "power",
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
                        "power-query",
                        "power-cycle",
                        "power-on",
                        "power-off",
                    ],
                    "activities": [
                        "power",
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

        endpoints = [
            {
                "endpoint": _format_endpoint(link["ip_address"]),
                "subnet": link["subnet"]["cidr"],
            }
            for region_controller in region_controllers
            for iface in region_controller["interface_set"]
            for link in iface["links"]
            if "ip_address" in link
        ]

        # TODO dynamically determine whether the agent needs to run the proxy
        await workflow.execute_activity(
            "configure-http-proxy",
            {
                "endpoints": endpoints,
            },
            task_queue=input.task_queue,
            start_to_close_timeout=timedelta(seconds=30),
        )
