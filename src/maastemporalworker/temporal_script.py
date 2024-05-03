# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from logging import getLogger
import signal

from maasapiserver.common.db import Database
from maasapiserver.settings import read_config
from maasserver.workflow.worker import Worker as TemporalWorker
from maastemporalworker.workflow.commission import CommissionNWorkflow
from maastemporalworker.workflow.configure import (
    ConfigureAgentActivity,
    ConfigureAgentWorkflow,
)
from maastemporalworker.workflow.deploy import DeployNWorkflow
from maastemporalworker.workflow.msm import (
    MSMConnectorActivity,
    MSMEnrolSiteWorkflow,
    MSMHeartbeatWorkflow,
    MSMWithdrawWorkflow,
)

log = getLogger()


async def _start_temporal_workers(workers: list[TemporalWorker]) -> None:
    futures = []
    for w in workers:
        futures.append(w.run())
    await asyncio.wait(futures)


async def _stop_temporal_workers(workers: list[TemporalWorker]) -> None:
    futures = []
    for w in workers:
        futures.append(w.stop())
    await asyncio.wait(futures)


async def main() -> None:
    # TODO check that Temporal is active
    log.info("starting region temporal-worker process")
    config = read_config()
    log.debug("connecting to MAAS DB")
    db = Database(config.db, echo=config.debug_queries)
    log.debug("connecting to Temporal server")

    configure_activity = ConfigureAgentActivity(db)
    msm_activity = MSMConnectorActivity(db)

    temporal_workers = [
        # All regions listen to a shared task queue. The first to pick up a task will execute it.
        TemporalWorker(
            task_queue="region",
            workflows=[
                # Configuration workflows
                ConfigureAgentWorkflow,
                # Lifecycle workflows
                DeployNWorkflow,
                CommissionNWorkflow,
                # MSM Connector service
                MSMEnrolSiteWorkflow,
                MSMWithdrawWorkflow,
                MSMHeartbeatWorkflow,
            ],
            activities=[
                # Configuration activities
                configure_activity.get_rack_controller_vlans,
                configure_activity.get_region_controller_endpoints,
                # MSM connector activities
                msm_activity.send_enrol,
                msm_activity.check_enrol,
                msm_activity.set_enrol,
                msm_activity.get_heartbeat_data,
                msm_activity.send_heartbeat,
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
