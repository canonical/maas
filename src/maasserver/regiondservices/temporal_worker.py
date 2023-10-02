# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Temporal Worker service."""

import asyncio

from twisted.application.service import Service
from twisted.internet.asyncioreactor import AsyncioSelectorReactor
from twisted.internet.defer import Deferred, inlineCallbacks, returnValue

from maasserver.config import RegionConfiguration
from maasserver.models.user import create_auth_token, get_auth_tokens
from maasserver.service_monitor import service_monitor, SERVICE_STATE
from maasserver.utils.threads import deferToDatabase
from maasserver.worker_user import get_worker_user
from maasserver.workflow.api_activities import MAASAPIActivities
from maasserver.workflow.commission import CommissionNWorkflow
from maasserver.workflow.configure import ConfigureWorkerPoolWorkflow
from maasserver.workflow.deploy import DeployNWorkflow
from maasserver.workflow.power import PowerNWorkflow
from maasserver.workflow.worker import Worker


class TemporalWorkerService(Service):
    def __init__(self, reactor):
        super().__init__()

        self.loop = None
        if isinstance(reactor, AsyncioSelectorReactor):
            self.loop = asyncio.get_event_loop()
        else:  # handle crochet reactor
            self.loop = asyncio.new_event_loop()

    def get_token(self):
        user = get_worker_user()
        for token in reversed(get_auth_tokens(user)):
            return token
        else:
            return create_auth_token(user)

    def get_maas_url(self):
        with RegionConfiguration.open() as config:
            base_url = config.maas_url
        return base_url

    @inlineCallbacks
    def startService(self):
        temporal_status = SERVICE_STATE.UNKNOWN
        while temporal_status != SERVICE_STATE.ON:
            status = yield service_monitor.getServiceState(
                "temporal", now=True
            )
            temporal_status = status.active_state

        maas_url = yield deferToDatabase(self.get_maas_url)
        token = yield deferToDatabase(self.get_token)

        maas_api_activities = MAASAPIActivities(url=maas_url, token=token)

        self.worker = Worker(
            workflows=[
                ConfigureWorkerPoolWorkflow,
                CommissionNWorkflow,
                DeployNWorkflow,
                PowerNWorkflow,
            ],
            activities=[
                maas_api_activities.get_rack_controller,
                maas_api_activities.switch_boot_order,
            ],
        )

        task = self.loop.create_task(self.worker.run())
        returnValue(Deferred.fromFuture(task))

    def stopService(self):
        if hasattr(self, "worker"):
            task = self.loop.create_task(self.worker.stop())
            return Deferred.fromFuture(task)
