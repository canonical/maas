# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Region controller service.

A service that controls external services on a MAAS region controller. This
service runs only on the master regiond process for a region controller.

DNS:
    The regiond process listens for messages from Postgres on channel
    'sys_dns'. Any time a message is received on that channel the DNS is marked
    as requiring an update. Once marked for update the DNS configuration is
    updated and bind9 is told to reload.

Proxy:
    The regiond process listens for messages from Postgres on channel
    'sys_proxy'. Any time a message is received on that channel the maas-proxy
    is marked as requiring an update. Once marked for update the proxy
    configuration is updated and maas-proxy is told to reload.

Vault migration restart:
    The regiond process listens for messages from Postgres on channel
    'sys_vault_migration'. Any time a message is received, regiond eventloop
    is restarted to make sure no regions will try to access secrets table.
"""

import logging

from twisted.application.service import Service
from twisted.internet import reactor
from twisted.internet.defer import DeferredList
from twisted.internet.task import LoopingCall
from twisted.names.client import Resolver

from maasserver import eventloop
from maasserver.proxyconfig import proxy_update_config
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import asynchronous, FOREVER

log = LegacyLogger()


class DNSReloadError(Exception):
    """Error raised when bind never fully reloads the zone."""


class RegionControllerService(Service):
    """Control services managed by the master region controller."""

    def __init__(
        self,
        postgresListener,
        dbtasks,
        clock=reactor,
        retryOnFailure=True,
    ):
        super().__init__()
        self.clock = clock
        self.retryOnFailure = retryOnFailure
        self.processing = LoopingCall(self.process)
        self.processing.clock = self.clock
        self.processingDefer = None
        self.needsDNSUpdate = True
        self.needsProxyUpdate = False
        self._dns_updates = []
        self._queued_updates = []
        self._dns_update_in_progress = False
        self._dns_requires_full_reload = True
        self._dns_latest_serial = None
        self.postgresListener = postgresListener
        self.dbtasks = dbtasks
        self.dnsResolver = Resolver(
            resolv=None,
            servers=[("127.0.0.1", 53)],
            timeout=(1,),
            reactor=clock,
        )
        self.previousSerial = None

    @asynchronous(timeout=FOREVER)
    def startService(self):
        """Start listening for messages."""
        super().startService()
        self.postgresListener.register("sys_proxy", self.markProxyForUpdate)
        self.postgresListener.register(
            "sys_vault_migration", self.restartRegion
        )
        self.postgresListener.events.connected.registerHandler(
            self.markAllForUpdate
        )

    @asynchronous(timeout=FOREVER)
    def stopService(self):
        """Close the controller."""
        super().stopService()
        self.postgresListener.events.connected.unregisterHandler(
            self.markAllForUpdate
        )
        self.postgresListener.unregister("sys_proxy", self.markProxyForUpdate)
        self.postgresListener.unregister(
            "sys_vault_migration", self.restartRegion
        )
        if self.processingDefer is not None:
            self.processingDefer, d = None, self.processingDefer
            self.processing.stop()
            return d

    def markAllForUpdate(self):
        self.markProxyForUpdate(None, None)

    def markProxyForUpdate(self, channel, message):
        """Called when the `sys_proxy` message is received."""
        self.needsProxyUpdate = True
        self.startProcessing()

    def restartRegion(self, channel, message):
        """Restart region eventloop on vault migration notification."""
        logging.getLogger(__name__).info(
            "Received migration restart notification."
        )
        eventloop.restart()

    def startProcessing(self):
        """Start the process looping call."""
        if not self.processing.running:
            self.processingDefer = self.processing.start(0.1, now=False)

    def process(self):
        """Process pending proxy updates."""

        def _onFailureRetry(failure, attr):
            if self.retryOnFailure:
                setattr(self, attr, True)
            return failure

        def _clear_dynamic_dns_updates(d):
            if len(self._queued_updates) > 0:
                self._dns_updates = self._queued_updates
                self._queued_updates = []
                self.needsDNSUpdate = True
            else:
                self._dns_updates = []
            self._dns_requires_full_reload = False
            self._dns_update_in_progress = False
            return d

        defers = []
        if self.needsProxyUpdate:
            self.needsProxyUpdate = False
            d = proxy_update_config(reload_proxy=True)
            d.addCallback(lambda _: log.msg("Successfully configured proxy."))
            d.addErrback(_onFailureRetry, "needsProxyUpdate")
            d.addErrback(log.err, "Failed configuring proxy.")
            defers.append(d)
        if len(defers) == 0:
            self.processing.stop()
            self.processingDefer = None
        else:
            return DeferredList(defers)
