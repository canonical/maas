# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Temporal Worker service."""

import asyncio

from twisted.application.service import Service
from twisted.internet.asyncioreactor import AsyncioSelectorReactor
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue

from maasserver.service_monitor import service_monitor, SERVICE_STATE
from maasserver.workflow.commission import CommissionNWorkflow
from maasserver.workflow.configure import ConfigureWorkerPoolWorkflow
from maasserver.workflow.deploy import DeployNWorkflow
from maasserver.workflow.power import PowerNWorkflow
from maasserver.workflow.worker import Worker

_client = None


class TemporalWorkerService(Service):
    def __init__(self, reactor):
        super().__init__()

        self._loop = None
        if isinstance(reactor, AsyncioSelectorReactor):
            self._loop = asyncio.get_event_loop()
        else:  # handle crochet reactor
            self._loop = asyncio.new_event_loop()
        self.worker = Worker(
            workflows=[
                ConfigureWorkerPoolWorkflow,
                CommissionNWorkflow,
                DeployNWorkflow,
                PowerNWorkflow,
            ]
        )

    @inlineCallbacks
    def startService(self):
        temporal_status = SERVICE_STATE.UNKNOWN
        while temporal_status != SERVICE_STATE.ON:
            status = yield service_monitor.getServiceState(
                "temporal", now=True
            )
            temporal_status = status.active_state
        task = self._loop.create_task(self.worker.run())
        returnValue(Deferred.fromFuture(task))

    def stopService(self):
        task = self._loop.create_task(self.worker.stop())
        return Deferred.fromFuture(task)
