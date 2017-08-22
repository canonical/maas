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

Proxy:
    The regiond process listens for messages from Postgres on channel
    'sys_proxy'. Any time a message is recieved on that channel the maas-proxy
    is marked as requiring an update. Once marked for update the proxy
    configuration is updated and maas-proxy is told to reload.
"""

__all__ = [
    "RegionControllerService",
]

from maasserver.dns.config import dns_update_all_zones
from maasserver.proxyconfig import proxy_update_config
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
    pause,
)
from twisted.application.service import Service
from twisted.internet import reactor
from twisted.internet.defer import (
    DeferredList,
    inlineCallbacks,
)
from twisted.internet.task import LoopingCall
from twisted.names.client import Resolver


log = LegacyLogger()


class DNSReloadError(Exception):
    """Error raised when the bind never fully reloads the zone."""


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
        self.needsProxyUpdate = False
        self.postgresListener = postgresListener
        self.dnsResolver = Resolver(
            resolv=None, servers=[('127.0.0.1', 53)],
            timeout=(1,), reactor=clock)

    @asynchronous(timeout=FOREVER)
    def startService(self):
        """Start listening for messages."""
        super(RegionControllerService, self).startService()
        self.postgresListener.register("sys_dns", self.markDNSForUpdate)
        self.postgresListener.register("sys_proxy", self.markProxyForUpdate)

        # Update DNS and proxy on first start.
        self.markDNSForUpdate(None, None)
        self.markProxyForUpdate(None, None)

    @asynchronous(timeout=FOREVER)
    def stopService(self):
        """Close the controller."""
        super(RegionControllerService, self).stopService()
        self.postgresListener.unregister("sys_dns", self.markDNSForUpdate)
        self.postgresListener.unregister("sys_proxy", self.markProxyForUpdate)
        if self.processingDefer is not None:
            self.processingDefer, d = None, self.processingDefer
            self.processing.stop()
            return d

    def markDNSForUpdate(self, channel, message):
        """Called when the `sys_dns` message is received."""
        self.needsDNSUpdate = True
        self.startProcessing()

    def markProxyForUpdate(self, channel, message):
        """Called when the `sys_proxy` message is received."""
        self.needsProxyUpdate = True
        self.startProcessing()

    def startProcessing(self):
        """Start the process looping call."""
        if not self.processing.running:
            self.processingDefer = self.processing.start(0.1, now=False)

    def process(self):
        """Process the DNS and/or proxy update."""
        defers = []
        if self.needsDNSUpdate:
            self.needsDNSUpdate = False
            d = deferToDatabase(transactional(dns_update_all_zones))
            d.addCallback(self._check_serial)
            d.addCallback(
                lambda domains: log.msg(
                    "Successfully configured DNS "
                    "authoritative zones: %s." % (
                        ', '.join(domains))))
            d.addErrback(
                log.err,
                "Failed configuring DNS.")
            defers.append(d)
        if self.needsProxyUpdate:
            self.needsProxyUpdate = False
            d = proxy_update_config(reload_proxy=True)
            d.addCallback(
                lambda _: log.msg(
                    "Successfully configured proxy."))
            d.addErrback(
                log.err,
                "Failed configuring proxy.")
            defers.append(d)
        if len(defers) == 0:
            # Nothing more to do.
            self.processing.stop()
            self.processingDefer = None
        else:
            return DeferredList(defers)

    @inlineCallbacks
    def _check_serial(self, result):
        """Check that the serial of the domain is updated."""
        serial, domain_names = result
        not_matching_domains = set(domain_names)
        loop = 0
        while len(not_matching_domains) > 0 and loop != 30:
            for domain in list(not_matching_domains):
                try:
                    answers, _, _ = yield self.dnsResolver.lookupAuthority(
                        domain)
                except (ValueError, TimeoutError):
                    answers = []
                if len(answers) > 0:
                    if int(answers[0].payload.serial) == int(serial):
                        not_matching_domains.remove(domain)
            loop += 1
            yield pause(2)
        # 30 retries with 2 second pauses (aka. 60 seconds) has passed and
        # there still is a domain that has the wrong serial. For now just
        # raise the error, in the future we should take action and force
        # restart bind.
        if len(not_matching_domains) > 0:
            raise DNSReloadError(
                "Failed to reload DNS; serial mismatch "
                "on domains %s" % ', '.join(not_matching_domains))
        return domain_names
