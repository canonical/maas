# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
import logging
import signal

import structlog

from maasapiserver.settings import read_config
from maascommon.worker import set_max_workers_count
from maasservicelayer.db import Database
from maasservicelayer.db.locks import wait_for_startup
from maasservicelayer.logging.configure import configure_logging
from maasservicelayer.services import CacheForServices
from maastemporalworker.worker import REGION_TASK_QUEUE
from maastemporalworker.worker import Worker as TemporalWorker
from maastemporalworker.workflow.bootresource import (
    BootResourcesActivity,
    CheckBootResourcesStorageWorkflow,
    DeleteBootResourceWorkflow,
    DownloadBootResourceWorkflow,
    SyncBootResourcesWorkflow,
)
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
    PowerResetWorkflow,
)
from maastemporalworker.workflow.tag_evaluation import (
    TagEvaluationActivity,
    TagEvaluationWorkflow,
)
from maastemporalworker.workflow.utils import async_retry
from provisioningserver.utils.env import MAAS_ID


class MAASIDNotAvailableYetError(Exception):
    """Raised when the MAAS ID is not available yet."""

    pass


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


@async_retry(retries=10)
async def get_maas_id() -> str:
    maas_id = MAAS_ID.get()
    if maas_id is None:
        raise MAASIDNotAvailableYetError(
            f"{MAAS_ID.path} not found. Please ensure that the regiond process is healthy."
        )
    return maas_id


async def main() -> None:
    # TODO check that Temporal is active
    config = await read_config()
    # TODO: terrible. Refactor when maasserver will be dropped, please!
    set_max_workers_count(config.num_workers)

    configure_logging(
        level=logging.DEBUG if config.debug else logging.INFO,
        query_level=logging.DEBUG if config.debug else logging.WARNING,
    )

    log.info("starting region temporal-worker process")
    log.debug("connecting to MAAS DB")
    db = Database(config.db, echo=config.debug_queries)

    # In maasserver we have a startup lock. If it is set, we have to wait to start the worker as well.
    await wait_for_startup(db)

    log.debug("connecting to Temporal server")

    maas_id = await get_maas_id()
    services_cache = CacheForServices()

    boot_res_activity = BootResourcesActivity(db, services_cache)
    await boot_res_activity.init(region_id=maas_id)
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
            task_queue=REGION_TASK_QUEUE,
            workflows=[
                # Boot resources workflows
                CheckBootResourcesStorageWorkflow,
                DeleteBootResourceWorkflow,
                # DownloadBootResourceWorkflow is run by the region that executes SyncBootResourcesWorkflow to download
                # the image on its own storage. Then, DownloadBootResourceWorkflow is scheduled on the task queues of the
                # other regions if the HA is being used.
                DownloadBootResourceWorkflow,
                SyncBootResourcesWorkflow,
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
                PowerResetWorkflow,
                # Tag Evaluation workflows
                TagEvaluationWorkflow,
            ],
            activities=[
                # Boot resources activities
                boot_res_activity.download_bootresourcefile,
                boot_res_activity.get_bootresourcefile_endpoints,
                boot_res_activity.get_bootresourcefile_sync_status,
                # Configuration activities
                configure_activity.get_rack_controller_vlans,
                configure_activity.get_region_controller_endpoints,
                configure_activity.get_resolver_config,
                # Deploy activities
                deploy_activity.set_node_status,
                deploy_activity.get_boot_order,
                deploy_activity.set_node_failed,
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
                msm_activity.set_bootsource,
                msm_activity.get_bootsources,
                msm_activity.delete_bootsources,
                # Tag evaluation activities
                tag_evaluation_activity.evaluate_tag,
                # Power state activities
                power_activity.set_power_state,
            ],
        ),
        # Individual region controller worker
        TemporalWorker(
            task_queue=f"region:{maas_id}",
            workflows=[
                # Boot resources workflows
                CheckBootResourcesStorageWorkflow,
                DownloadBootResourceWorkflow,
            ],
            activities=[
                # Boot resources activities
                boot_res_activity.delete_bootresourcefile,
                boot_res_activity.download_bootresourcefile,
                boot_res_activity.check_disk_space,
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
