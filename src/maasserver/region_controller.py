# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Region controller service.

A service that controllers external services on the a MAAS region controller.
This service is ran only on the master regiond process for a region controller.

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

RBAC:
    The regiond process listens for messages from Postgres on channel
    'sys_rbac'. Any time a message is received on that channel the RBAC
    micro-service is marked as required a sync. Once marked for sync the
    RBAC micro-service will be pushed the changed information.

Vault migration restart:
    The regiond process listens for messages from Postgres on channel
    'sys_vault_migration'. Any time a message is received, regiond eventloop
    is restarted to make sure no regions will try to access secrets table.
"""


import logging
from operator import attrgetter

from twisted.application.service import Service
from twisted.internet import reactor
from twisted.internet.defer import DeferredList, inlineCallbacks
from twisted.internet.task import LoopingCall
from twisted.names.client import Resolver

from maasserver import eventloop, locks
from maasserver.dns.config import (
    dns_update_all_zones,
    process_dns_update_notify,
)
from maasserver.macaroon_auth import get_auth_info
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.rbacsync import RBAC_ACTION, RBACLastSync, RBACSync
from maasserver.models.resourcepool import ResourcePool
from maasserver.proxyconfig import proxy_update_config
from maasserver.rbac import RBACClient, Resource, SyncConflictError
from maasserver.secrets import SecretManager
from maasserver.service_monitor import service_monitor
from maasserver.triggers.models.dns_notifications import (
    DynamicDNSUpdateNotification,
)
from maasserver.utils import synchronised
from maasserver.utils.orm import transactional, with_connection
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import asynchronous, FOREVER, pause

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

    def __init__(
        self,
        postgresListener,
        dbtasks,
        clock=reactor,
        retryOnFailure=True,
        rbacRetryOnFailureDelay=10,
    ):
        """Initialise a new `RegionControllerService`.

        :param postgresListener: The `PostgresListenerService` that is running
            in this regiond process.
        """
        super().__init__()
        self.clock = clock
        self.retryOnFailure = retryOnFailure
        self.rbacRetryOnFailureDelay = rbacRetryOnFailureDelay
        self.processing = LoopingCall(self.process)
        self.processing.clock = self.clock
        self.processingDefer = None
        self.needsDNSUpdate = True  # reload DNS on start of region
        self.needsProxyUpdate = False
        self.needsRBACUpdate = False
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
        self.rbacClient = None
        self.rbacInit = False

    @asynchronous(timeout=FOREVER)
    def startService(self):
        """Start listening for messages."""
        super().startService()
        self.postgresListener.register("sys_dns", self.markDNSForUpdate)
        self.postgresListener.register(
            "sys_dns_updates", self.queueDynamicDNSUpdate
        )
        self.postgresListener.register("sys_proxy", self.markProxyForUpdate)
        self.postgresListener.register("sys_rbac", self.markRBACForUpdate)
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
        self.postgresListener.unregister("sys_dns", self.markDNSForUpdate)
        self.postgresListener.unregister("sys_proxy", self.markProxyForUpdate)
        self.postgresListener.unregister("sys_rbac", self.markRBACForUpdate)
        self.postgresListener.unregister(
            "sys_vault_migration", self.restartRegion
        )
        if self.processingDefer is not None:
            self.processingDefer, d = None, self.processingDefer
            self.processing.stop()
            return d

    def markAllForUpdate(self):
        self.markDNSForUpdate(None, None)
        self.markProxyForUpdate(None, None)
        self.markRBACForUpdate(None, None)

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

    def restartRegion(self, channel, message):
        """Restarts region eventloop when `sys_vault_migration` message is received."""
        logging.getLogger(__name__).info(
            "Received migration restart notification."
        )
        eventloop.restart()

    def queueDynamicDNSUpdate(self, channel, message):
        """
        Called when the `sys_dns_update` message is received
        and queues updates for existing domains.
        Since an uncatched exception would stop the processing of the notifications, we catch and log
        every exception at top level.
        """
        try:
            return self._queueDynamicDNSUpdate(channel, message)
        except Exception as e:
            log.warn(
                f"The message '{message}' might not have been processed correctly due to the exception: '{e}'"
            )

    def _queueDynamicDNSUpdate(self, channel, message):
        """
        The updates are offloaded to the DatabaseTasksService in order to
        process them in sequence and keep consuming the next postgres notifications.
        """

        def updateCallback(result):
            (new_updates, need_reload) = result
            self._dns_requires_full_reload = (
                self._dns_requires_full_reload or need_reload
            )
            if self._dns_update_in_progress:
                self._queued_updates += new_updates
            else:
                self._dns_updates += new_updates

        log.debug(f"Start processing dynamic DNS update '{message}'")

        notification = DynamicDNSUpdateNotification(message)
        if not notification.is_valid():
            log.warn(
                f"The dynamic dns update notification '{message}' is not valid. It will be dropped."
            )
            return

        self.dbtasks.deferTaskWithCallbacks(
            process_dns_update_notify,
            [updateCallback],
            notification.get_decoded_message(),
        )

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

        def _rbacFailure(failure, delay):
            log.err(failure, "Failed syncing resources to RBAC.")
            if delay:
                return pause(delay)

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

        def _set_latest_serial(result):
            if result:
                (serial, _, _) = result
                if (
                    not self._dns_latest_serial
                    or self._dns_latest_serial < serial
                ):
                    self._dns_latest_serial = serial
            return result

        defers = []
        if self.needsDNSUpdate:
            self.needsDNSUpdate = False
            self._dns_update_in_progress = True
            d = deferToDatabase(
                transactional(
                    dns_update_all_zones,
                ),
                dynamic_updates=self._dns_updates,
                requires_reload=self._dns_requires_full_reload,
            )
            d.addCallback(_clear_dynamic_dns_updates)
            d.addCallback(_set_latest_serial)
            d.addCallback(self._checkSerial)
            d.addCallback(self._logDNSReload)
            # Order here matters, first needsDNSUpdate is set then pass the
            # failure onto `_onDNSReloadFailure` to do the correct thing
            # with the DNS server.
            d.addErrback(_onFailureRetry, "needsDNSUpdate")
            d.addErrback(self._onDNSReloadFailure)
            d.addErrback(log.err, "Failed configuring DNS.")
            defers.append(d)
        if self.needsProxyUpdate:
            self.needsProxyUpdate = False
            d = proxy_update_config(reload_proxy=True)
            d.addCallback(lambda _: log.msg("Successfully configured proxy."))
            d.addErrback(_onFailureRetry, "needsProxyUpdate")
            d.addErrback(log.err, "Failed configuring proxy.")
            defers.append(d)
        if self.needsRBACUpdate:
            self.needsRBACUpdate = False
            d = deferToDatabase(self._rbacSync)
            d.addCallback(_rbacInit)
            d.addCallback(self._logRBACSync)
            d.addErrback(_onFailureRetry, "needsRBACUpdate")
            d.addErrback(
                _rbacFailure,
                self.rbacRetryOnFailureDelay if self.retryOnFailure else None,
            )
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
        serial, reloaded, domain_names = result

        # check that there is not a newer serial we should query instead
        if self._dns_latest_serial and self._dns_latest_serial > serial:
            return result

        if not reloaded:
            raise DNSReloadError(
                "Failed to reload DNS; timeout or rdnc command failed."
            )
        not_matching_domains = set(domain_names)
        loop = 0
        while len(not_matching_domains) > 0 and loop != 30:
            for domain in list(not_matching_domains):
                try:
                    answers, _, _ = yield self.dnsResolver.lookupAuthority(
                        domain
                    )
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
                "on domains %s" % ", ".join(not_matching_domains)
            )
        return result

    def _logDNSReload(self, result):
        """Log the reason DNS was reloaded."""
        if result is None:
            return None
        serial, _, domain_names = result
        if self.previousSerial is None:
            # This was the first load for starting the service.
            self.previousSerial = serial
            log.msg("Reloaded DNS configuration; regiond started.")
        else:
            # This is a reload since the region has been running. Get the
            # reason for the reload.

            def _logReason(reasons):
                if len(reasons) == 0:
                    msg = (
                        "Reloaded DNS configuration; previous failure (retry)"
                    )
                elif len(reasons) == 1:
                    msg = "Reloaded DNS configuration; %s" % reasons[0]
                else:
                    msg = "Reloaded DNS configuration: \n" + "\n".join(
                        " * %s" % reason for reason in reasons
                    )
                log.msg(msg)

            d = deferToDatabase(
                self._getReloadReasons, self.previousSerial, serial
            )
            d.addCallback(_logReason)
            d.addErrback(log.err, "Failed to log reason for DNS reload")

            self.previousSerial = serial
            return d

    def _onDNSReloadFailure(self, failure):
        """Force kill and restart bind9."""
        failure.trap(DNSReloadError)
        if not self.retryOnFailure:
            return failure
        log.err(failure, "Failed configuring DNS; killing and restarting")
        d = service_monitor.killService("bind9")
        d.addErrback(log.err, "Failed to kill and restart DNS.")
        return d

    @transactional
    def _getReloadReasons(self, previousSerial, currentSerial):
        return [
            publication.source
            for publication in DNSPublication.objects.filter(
                serial__gt=previousSerial, serial__lte=currentSerial
            ).order_by("-id")
        ]

    def _getRBACClient(self):
        """Return the `RBACClient`.

        This tries to use an already held client when initialized because the
        cookiejar will be updated with the already authenticated macaroon.
        """
        url = (
            SecretManager()
            .get_composite_secret("external-auth", default={})
            .get("rbac-url")
        )
        if not url:
            # RBAC is not enabled (or no longer enabled).
            self.rbacClient = None
            return None

        auth_info = get_auth_info()
        if (
            self.rbacClient is None
            or self.rbacClient._url != url
            or self.rbacClient._auth_info != auth_info
        ):
            self.rbacClient = RBACClient(url, auth_info)

        return self.rbacClient

    @with_connection  # Needed by the following lock.
    @synchronised(locks.rbac_sync)
    @transactional
    def _rbacSync(self):
        """Sync the RBAC information."""
        # Currently this whole method is scoped to dealing with
        # 'resource-pool'. As more items are synced to RBAC this
        # will need to be adjusted to handle multiple.
        changes = RBACSync.objects.changes("resource-pool")
        if not changes and self.rbacInit:
            # Nothing has changed, meaning another region already took care
            # of performing the update.
            return None

        client = self._getRBACClient()
        if client is None:
            # RBAC is disabled, do nothing.
            RBACSync.objects.clear("resource-pool")  # Changes not needed.
            return None

        # Push the resource information based on the last sync.
        new_sync_id = None
        try:
            last_sync = RBACLastSync.objects.get(resource_type="resource-pool")
        except RBACLastSync.DoesNotExist:
            last_sync = None
        if last_sync is None or self._rbacNeedsFull(changes):
            # First sync or requires a full sync.
            resources = [
                Resource(identifier=rpool.id, name=rpool.name)
                for rpool in ResourcePool.objects.order_by("id")
            ]
            new_sync_id = client.update_resources(
                "resource-pool", updates=resources
            )
        else:
            # Send only the difference of what has been changed.
            updates, removals = self._rbacDifference(changes)
            if updates or removals:
                try:
                    new_sync_id = client.update_resources(
                        "resource-pool",
                        updates=updates,
                        removals=removals,
                        last_sync_id=last_sync.sync_id,
                    )
                except SyncConflictError:
                    # Issue occurred syncing, push all information.
                    resources = [
                        Resource(identifier=rpool.id, name=rpool.name)
                        for rpool in ResourcePool.objects.order_by("id")
                    ]
                    new_sync_id = client.update_resources(
                        "resource-pool", updates=resources
                    )
        if new_sync_id:
            RBACLastSync.objects.update_or_create(
                resource_type="resource-pool",
                defaults={"sync_id": new_sync_id},
            )

        if not self.rbacInit:
            # This was initial sync on start-up.
            RBACSync.objects.clear("resource-pool")
            return []

        # Return the changes and clear the table, so new changes will be
        # tracked. Being inside a transaction allows us not to worry about
        # a new change already existing with the clear.
        changes = [change.source for change in changes]
        RBACSync.objects.clear("resource-pool")
        return changes

    def _logRBACSync(self, changes):
        """Log the reason RBAC was synced."""
        if changes is None:
            return None
        if len(changes) == 0:
            # This was the first load for starting the service.
            log.msg("Synced RBAC service; regiond started.")
        else:
            # This is a sync since the region has been running. Get the
            # reason for the reload.
            if len(changes) == 1:
                msg = "Synced RBAC service; %s" % changes[0]
            else:
                msg = "Synced RBAC service: \n" + "\n".join(
                    " * %s" % reason for reason in changes
                )
            log.msg(msg)

    def _rbacNeedsFull(self, changes):
        """Return True if any changes are marked requiring full sync."""
        return any(change.action == RBAC_ACTION.FULL for change in changes)

    def _rbacDifference(self, changes):
        """Return the only the changes that need to be pushed to RBAC."""
        # Removals are calculated first. A removal is never followed by an
        # update and `resource_id` is never re-used.
        removals = {
            change.resource_id
            for change in changes
            if change.action == RBAC_ACTION.REMOVE
        }
        # Changes are ordered from oldest to lates. The latest change will
        # be the last item of that `resource_id` in the dictionary.
        updates = {
            change.resource_id: change.resource_name
            for change in changes
            if (
                change.resource_id not in removals
                and change.action != RBAC_ACTION.REMOVE
            )
        }
        # Any additions with also a removal is not sync to RBAC.
        for change in changes:
            if change.action == RBAC_ACTION.ADD:
                if change.resource_id in removals:
                    removals.remove(change.resource_id)
        return (
            sorted(
                (
                    Resource(identifier=res_id, name=res_name)
                    for res_id, res_name in updates.items()
                ),
                key=attrgetter("identifier"),
            ),
            removals,
        )
