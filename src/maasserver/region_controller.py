# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Region controller service.

A service that controllers external services on the a MAAS region controller.
This service is ran only on the master regiond process for a region controller.

DNS:
    The regiond process listens for messages from Postgres on channel
    'sys_dns'. Any time a message is recieved on that channel the DNS is marked
    as requiring an update. Once marked for update the DNS configuration is
    updated and bind9 is told to reload.
"""

__all__ = [
    "RegionControllerService",
]

from maasserver.dns.config import dns_update_all_zones
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
)
from twisted.application.service import Service
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.python import log


class RegionControllerService(Service):
    """
    A service that controllers external services that are in MAAS's control on
    a region controller. This service is ran only on the master regiond process
    for a region controller.

    See module documentation for more details.
    """

    def __init__(self, postgresListener, clock=reactor):
        """Initialise a new `RegionControllerService`.

        :param postgresListener: The `PostgresListenerService` that is running
            in this regiond process.
        """
        super(RegionControllerService, self).__init__()
        self.clock = clock
        self.processing = LoopingCall(self.process)
        self.processing.clock = self.clock
        self.processingDefer = None
        self.needsDNSUpdate = False
        self.postgresListener = postgresListener

    @asynchronous(timeout=FOREVER)
    def startService(self):
        """Start listening for messages."""
        super(RegionControllerService, self).startService()
        self.postgresListener.register("sys_dns", self.markDNSForUpdate)

        # Update DNS on first start.
        self.markDNSForUpdate(None, None)

    @asynchronous(timeout=FOREVER)
    def stopService(self):
        """Close the controller."""
        super(RegionControllerService, self).stopService()
        self.postgresListener.unregister("sys_dns", self.markDNSForUpdate)
        if self.processingDefer is not None:
            self.processingDefer, d = None, self.processingDefer
            self.processing.stop()
            return d

    def markDNSForUpdate(self, channel, message):
        """Called when the `sys_dns` message is received."""
        self.needsDNSUpdate = True
        self.startProcessing()

    def startProcessing(self):
        """Start the process looping call."""
        if not self.processing.running:
            self.processingDefer = self.processing.start(0.1, now=False)

    def process(self):
        """Process the DNS update."""
        if self.needsDNSUpdate:
            self.needsDNSUpdate = False
            d = deferToDatabase(transactional(dns_update_all_zones))
            d.addCallback(
                lambda _: log.msg(
                    "Successfully configured DNS."))
            d.addErrback(
                log.err,
                "Failed configuring DNS.")
            return d
        else:
            # Nothing more to do.
            self.processing.stop()
            self.processingDefer = None
