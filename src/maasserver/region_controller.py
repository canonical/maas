# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
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

RBAC:
    The regiond process listens for messages from Postgres on channel
    'sys_rbac'. Any time a message is recieved on that channel the RBAC
    micro-service is marked as required a sync. Once marked for sync the
    RBAC micro-service will be pushed the changed information.
"""

__all__ = [
    "RegionControllerService",
]

from maasserver import locks
from maasserver.dns.config import dns_update_all_zones
from maasserver.macaroon_auth import (
    get_auth_info,
    RBACClient,
    Resource,
)
from maasserver.models.config import Config
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.rbacsync import RBACSync
from maasserver.models.resourcepool import ResourcePool
from maasserver.proxyconfig import proxy_update_config
from maasserver.utils import synchronised
from maasserver.utils.orm import (
    transactional,
    with_connection,
)
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

    def __init__(self, postgresListener, clock=reactor, retryOnFailure=True):
        """Initialise a new `RegionControllerService`.

        :param postgresListener: The `PostgresListenerService` that is running
            in this regiond process.
        """
        super(RegionControllerService, self).__init__()
        self.clock = clock
        self.retryOnFailure = retryOnFailure
        self.processing = LoopingCall(self.process)
        self.processing.clock = self.clock
        self.processingDefer = None
        self.needsDNSUpdate = False
        self.needsProxyUpdate = False
        self.needsRBACUpdate = False
        self.postgresListener = postgresListener
        self.dnsResolver = Resolver(
            resolv=None, servers=[('127.0.0.1', 53)],
            timeout=(1,), reactor=clock)
        self.previousSerial = None
        self.rbacClient = None
        self.rbacInit = False

    @asynchronous(timeout=FOREVER)
    def startService(self):
        """Start listening for messages."""
        super(RegionControllerService, self).startService()
        self.postgresListener.register("sys_dns", self.markDNSForUpdate)
        self.postgresListener.register("sys_proxy", self.markProxyForUpdate)
        self.postgresListener.register("sys_rbac", self.markRBACForUpdate)

        # Update DNS and proxy on first start.
        self.markDNSForUpdate(None, None)
        self.markProxyForUpdate(None, None)
        self.markRBACForUpdate(None, None)

    @asynchronous(timeout=FOREVER)
    def stopService(self):
        """Close the controller."""
        super(RegionControllerService, self).stopService()
        self.postgresListener.unregister("sys_dns", self.markDNSForUpdate)
        self.postgresListener.unregister("sys_proxy", self.markProxyForUpdate)
        self.postgresListener.unregister("sys_rbac", self.markRBACForUpdate)
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

    def markRBACForUpdate(self, channel, message):
        """Called when the `sys_rbac` message is received."""
        self.needsRBACUpdate = True
        self.startProcessing()

    def startProcessing(self):
        """Start the process looping call."""
        if not self.processing.running:
            self.processingDefer = self.processing.start(0.1, now=False)

    def process(self):
        """Process the DNS and/or proxy update."""

        def _onFailureRetry(failure, attr):
            """Retry update on failure.

            Doesn't mask the failure, the failure is still raised.
            """
            if self.retryOnFailure:
                setattr(self, attr, True)
            return failure

        def _rbacInit(result):
            """Mark initialization took place."""
            if result is not None:
                # A sync occurred.
                self.rbacInit = True
            return result

        defers = []
        if self.needsDNSUpdate:
            self.needsDNSUpdate = False
            d = deferToDatabase(transactional(dns_update_all_zones))
            d.addCallback(self._checkSerial)
            d.addCallback(self._logDNSReload)
            d.addErrback(_onFailureRetry, 'needsDNSUpdate')
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
            d.addErrback(_onFailureRetry, 'needsProxyUpdate')
            d.addErrback(
                log.err,
                "Failed configuring proxy.")
            defers.append(d)
        if self.needsRBACUpdate:
            self.needsRBACUpdate = False
            d = deferToDatabase(self._rbacSync)
            d.addCallback(_rbacInit)
            d.addCallback(self._logRBACSync)
            d.addErrback(_onFailureRetry, 'needsRBACUpdate')
            d.addErrback(
                log.err,
                "Failed syncing resources to RBAC.")
            defers.append(d)
        if len(defers) == 0:
            # Nothing more to do.
            self.processing.stop()
            self.processingDefer = None
        else:
            return DeferredList(defers)

    @inlineCallbacks
    def _checkSerial(self, result):
        """Check that the serial of the domain is updated."""
        if result is None:
            return None
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
        return serial, domain_names

    def _logDNSReload(self, result):
        """Log the reason DNS was reloaded."""
        if result is None:
            return None
        serial, domain_names = result
        if self.previousSerial is None:
            # This was the first load for starting the service.
            self.previousSerial = serial
            log.msg(
                "Reloaded DNS configuration; regiond started.")
        else:
            # This is a reload since the region has been running. Get the
            # reason for the reload.

            def _logReason(reasons):
                if len(reasons) == 1:
                    msg = "Reloaded DNS configuration; %s" % reasons[0]
                else:
                    msg = 'Reloaded DNS configuration: \n' + '\n'.join(
                        ' * %s' % reason
                        for reason in reasons
                    )
                log.msg(msg)

            d = deferToDatabase(
                self._getReloadReasons, self.previousSerial, serial)
            d.addCallback(_logReason)
            d.addErrback(log.err, "Failed to log reason for DNS reload")

            self.previousSerial = serial
            return d

    @transactional
    def _getReloadReasons(self, previousSerial, currentSerial):
        return [
            publication.source
            for publication in DNSPublication.objects.filter(
                serial__gt=previousSerial,
                serial__lte=currentSerial).order_by('-id')
        ]

    def _getRBACClient(self):
        """Return the `RBACClient`.

        This tries to use an already held client when initialized because the
        cookiejar will be updated with the already authenticated macaroon.
        """
        url = Config.objects.get_config('rbac_url')
        if not url:
            # RBAC is not enabled (or no longer enabled).
            self.rbacClient = None
            return None

        auth_info = get_auth_info()
        if (self.rbacClient is None or
                self.rbacClient._url != url or
                self.rbacClient._auth_info != auth_info):
            self.rbacClient = RBACClient(url, auth_info)

        return self.rbacClient

    @with_connection  # Needed by the following lock.
    @synchronised(locks.rbac_sync)
    @transactional
    def _rbacSync(self):
        """Sync the RBAC information."""
        changes = RBACSync.objects.changes()
        if not changes and self.rbacInit:
            # Nothing has changed, meaning another region already took care
            # of performing the update.
            return None

        client = self._getRBACClient()
        if client is None:
            # RBAC is disabled, do nothing.
            RBACSync.objects.clear()  # Changes not needed, RBAC disabled.
            return None

        # XXX blake_r 2018-10-04 - This can be smarter by looking at the
        # action and resource_type information in the changes. At the moment
        # the RBAC service doesn't have a robust changes API, so it just
        # pushes all the information.
        resources = [
            Resource(identifier=rpool.id, name=rpool.name)
            for rpool in ResourcePool.objects.all()
        ]
        client.put_resources('resource-pool', resources)

        if not self.rbacInit:
            # This was initial sync on start-up.
            RBACSync.objects.clear()
            return []

        # Return the changes and clear the table, so new changes will be
        # tracked. Being inside a transaction allows us not to worry about
        # a new change already existing with the clear.
        changes = [
            change.source
            for change in changes
        ]
        RBACSync.objects.clear()
        return changes

    def _logRBACSync(self, changes):
        """Log the reason RBAC was synced."""
        if changes is None:
            return None
        if len(changes) == 0:
            # This was the first load for starting the service.
            log.msg(
                "Synced RBAC service; regiond started.")
        else:
            # This is a sync since the region has been running. Get the
            # reason for the reload.
            if len(changes) == 1:
                msg = "Synced RBAC service; %s" % changes[0]
            else:
                msg = 'Synced RBAC service: \n' + '\n'.join(
                    ' * %s' % reason
                    for reason in changes
                )
            log.msg(msg)
