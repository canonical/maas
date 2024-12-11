# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
import logging
import signal

import structlog

from maasapiserver.settings import read_config
from maasserver.workflow.worker import Worker as TemporalWorker
from maasservicelayer.db import Database
from maasservicelayer.logging.configure import configure_logging
from maasservicelayer.services import CacheForServices
from maastemporalworker.workflow.commission import CommissionNWorkflow
from maastemporalworker.workflow.configure import (
    ConfigureAgentActivity,
    ConfigureAgentWorkflow,
)
from maastemporalworker.workflow.deploy import (
    DeployActivity,
    DeployManyWorkflow,
    DeployWorkflow,
)
from maastemporalworker.workflow.dhcp import (
    ConfigureDHCPForAgentWorkflow,
    ConfigureDHCPWorkflow,
    DHCPConfigActivity,
)
from maastemporalworker.workflow.dns import (
    ConfigureDNSWorkflow,
    DNSConfigActivity,
)
from maastemporalworker.workflow.msm import (
    MSMConnectorActivity,
    MSMEnrolSiteWorkflow,
    MSMHeartbeatWorkflow,
    MSMTokenRefreshWorkflow,
    MSMWithdrawWorkflow,
)
from maastemporalworker.workflow.power import (
    PowerActivity,
    PowerCycleWorkflow,
    PowerManyWorkflow,
    PowerOffWorkflow,
    PowerOnWorkflow,
    PowerQueryWorkflow,
)
from maastemporalworker.workflow.tag_evaluation import (
    TagEvaluationActivity,
    TagEvaluationWorkflow,
)
from provisioningserver.utils.env import MAAS_ID

log = structlog.getLogger()


async def _start_temporal_workers(workers: list[TemporalWorker]) -> None:
    tasks = []
    for w in workers:
        tasks.append(asyncio.create_task(w.run()))
    await asyncio.wait(tasks)


async def _stop_temporal_workers(workers: list[TemporalWorker]) -> None:
    tasks = []
    for w in workers:
        tasks.append(asyncio.create_task(w.stop()))
    await asyncio.wait(tasks)


async def main() -> None:
    # TODO check that Temporal is active
    config = await read_config()
    configure_logging(
        level=logging.DEBUG if config.debug else logging.INFO,
        query_level=logging.DEBUG if config.debug else logging.WARNING,
    )

    log.info("starting region temporal-worker process")
    log.debug("connecting to MAAS DB")
    db = Database(config.db, echo=config.debug_queries)
    log.debug("connecting to Temporal server")

    maas_id = MAAS_ID.get()

    services_cache = CacheForServices()
    configure_activity = ConfigureAgentActivity(db, services_cache)
    msm_activity = MSMConnectorActivity(db, services_cache)
    tag_evaluation_activity = TagEvaluationActivity(db, services_cache)
    deploy_activity = DeployActivity(db, services_cache)
    dhcp_activity = DHCPConfigActivity(db, services_cache)
    dns_activity = DNSConfigActivity(db, services_cache)
    power_activity = PowerActivity(db, services_cache)

    temporal_workers = [
        # All regions listen to a shared task queue. The first to pick up a task will execute it.
        TemporalWorker(
            task_queue="region",
            workflows=[
                # Configuration workflows
                ConfigureAgentWorkflow,
                ConfigureDHCPWorkflow,
                ConfigureDHCPForAgentWorkflow,
                ConfigureDNSWorkflow,
                # Lifecycle workflows
                DeployManyWorkflow,
                DeployWorkflow,
                CommissionNWorkflow,
                # MSM Connector service
                MSMEnrolSiteWorkflow,
                MSMWithdrawWorkflow,
                MSMHeartbeatWorkflow,
                MSMTokenRefreshWorkflow,
                # Power workflows
                PowerOnWorkflow,
                PowerOffWorkflow,
                PowerCycleWorkflow,
                PowerQueryWorkflow,
                PowerManyWorkflow,
                # Tag Evaluation workflows
                TagEvaluationWorkflow,
            ],
            activities=[
                # Configuration activities
                configure_activity.get_rack_controller_vlans,
                configure_activity.get_region_controller_endpoints,
                # Deploy activities
                deploy_activity.set_node_status,
                deploy_activity.get_boot_order,
                # DHCP activities
                dhcp_activity.find_agents_for_updates,
                dhcp_activity.fetch_hosts_for_update,
                dhcp_activity.get_omapi_key,
                # DNS activities
                dns_activity.get_changes_since_current_serial,
                dns_activity.get_region_controllers,
                # MSM connector activities,
                msm_activity.check_enrol,
                msm_activity.get_enrol,
                msm_activity.get_heartbeat_data,
                msm_activity.refresh_token,
                msm_activity.send_enrol,
                msm_activity.send_heartbeat,
                msm_activity.set_enrol,
                msm_activity.verify_token,
                # Tag evaluation activities
                tag_evaluation_activity.evaluate_tag,
                # Power state activities
                power_activity.set_power_state,
            ],
        ),
        # Individual region controller worker
        TemporalWorker(
            task_queue=f"region:{maas_id}",
            activities=[
                # dns activities
                dns_activity.full_reload_dns_configuration,
                dns_activity.dynamic_update_dns_configuration,
                dns_activity.check_serial_update,
            ],
        ),
    ]

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.ensure_future(
                _stop_temporal_workers(temporal_workers)
            ),
        )

    log.info("temporal-worker started")
    await _start_temporal_workers(temporal_workers)


def run():
    asyncio.run(main())
