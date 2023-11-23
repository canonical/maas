from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from maasserver.workflow.api_client import MAASAPIClient


@dataclass
class GetRackControllerInput:
    system_id: str


class ConfigureWorkerPoolActivity(MAASAPIClient):
    @activity.defn(name="get-rack-controller")
    async def get_rack_controller(self, input: GetRackControllerInput):
        url = f"{self.url}/api/2.0/rackcontrollers/{input.system_id}/"
        return await self.request_async("GET", url)


@dataclass
class ConfigureWorkerPoolInput:
    system_id: str
    task_queue: str


@workflow.defn(name="configure-agent", sandboxed=False)
class ConfigureWorkerPoolWorkflow:
    """A ConfigureWorkerPool workflow to setup MAAS Agent workers"""

    @workflow.run
    async def run(self, input: ConfigureWorkerPoolInput) -> None:
        result = await workflow.execute_activity(
            "get-rack-controller",
            GetRackControllerInput(input.system_id),
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                maximum_attempts=5,
            ),
        )

        interface_set = result["interface_set"]
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
