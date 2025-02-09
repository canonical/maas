# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Rack controller service.

A service that controllers the external services on a rack controller. Using
the Postgres listening service, it takes messages from the notifier and
performs the required actions.

How it works:
    Each regiond process listens for messages from Postgres on channel
    'sys_core_{id}', where 'id' is the ID of the running process in Postgres.
    Messages are passed on this queue to the region informing the region
    what action it needs to perform.

    List of actions:
        watch_{id}: 'id' is the ID for a rack controller that this service
            should start listening for messages from Postgres. A rack
            controller is only being watched by one regiond process in the
            entire MAAS deployment. When the watching regiond process dies
            or drops the connection to the rack controller a new regiond
            process will be selected from the database and alerted.
        unwatch_{id}: 'id' is the ID for a rack controller that this service
            should stop listening for messages from Postgres. This occurs
            when another regiond process takes control of this rack controller
            or when the rack controller disconnects from this regiond process.

DHCP:
    Once a 'watch_{id}' message is sent to this process it will start listening
    for messages on 'sys_dhcp_{id}' channel and set that rack controller as
    needing an update. Any time a message is received on this queue that rack
    controller is marked as needing an update.
"""

from functools import partial
import os

from twisted.application.service import Service
from twisted.internet import reactor
from twisted.internet.defer import CancelledError, maybeDeferred
from twisted.internet.task import LoopingCall

from maasserver import dhcp
from maasserver.listener import PostgresListenerUnregistrationError
from maasserver.models.node import RackController
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils.twisted import asynchronous, callOut, FOREVER

log = LegacyLogger()


class RackControllerService(Service):
    """
    A service that controllers the external services that MAAS runs. Using the
    Postgres listening service, it takes messages from the notifier and
    performs the required actions.

    See module documentation for more details.
    """

    PROCESSING_DELAY = 0.1

    def __init__(self, ipcWorker, postgresListener, clock=reactor):
        """Initialise a new `RackControllerService`.

        :param postgresListener: The `PostgresListenerService` that is running
            in this regiond process.
        """
        super().__init__()
        self.clock = clock
        self.starting = None
        self.processing = LoopingCall(self.process)
        self.processing.clock = self.clock
        self.processingDone = None
        self.watching = set()
        self.needsDHCPUpdate = set()
        self.ipcWorker = ipcWorker
        self.postgresListener = postgresListener

    @asynchronous(timeout=FOREVER)
    def startService(self):
        """Start listening for messages."""
        super().startService()

        def cb_registerWithPostgres(processId):
            # Register the coreHandler with postgres.
            self.processId = processId
            self.postgresListener.register(
                "sys_core_%d" % self.processId, self.coreHandler
            )
            return self.postgresListener.channelRegistrarDone

        @transactional
        def cb_getManagingProcesses(result):
            # Return the list of rack controllers that this process is
            # managing. This is done to be sure that no messages where missed
            # while this service was still starting.
            return sorted(
                RackController.objects.filter(
                    managing_process=self.processId
                ).values_list("id", flat=True)
            )

        def cb_handlerMissedMessages(rack_ids):
            # Call the handler as if it came from the postgres listener.
            for rack_id in rack_ids:
                self.coreHandler(
                    "sys_core_%d" % self.processId, "watch_%d" % rack_id
                )

        def cb_clearStarting(_):
            # Clear starting as its now started.
            self.starting = None

        def eb_cancelled(failure):
            # Catch cancelled.
            failure.trap(CancelledError)
            self.starting = None

        self.starting = self.ipcWorker.processId.get()
        self.starting.addCallback(cb_registerWithPostgres)
        self.starting.addCallback(
            partial(deferToDatabase, cb_getManagingProcesses)
        )
        self.starting.addCallback(cb_handlerMissedMessages)
        self.starting.addCallback(cb_clearStarting)
        self.starting.addErrback(eb_cancelled)
        # No final errback because we want this to crash hard. This is really
        # bad if this happens as MAAS will stop working.
        return self.starting

    @asynchronous(timeout=FOREVER)
    def stopService(self):
        """Close the controller."""
        super().stopService()

        def cleanUp():
            # Unregister the core handler.
            try:
                self.postgresListener.unregister(
                    "sys_core_%s" % self.processId, self.coreHandler
                )
            except PostgresListenerUnregistrationError:
                # Error is acceptable as it might not have been called yet.
                pass

            # Unregister all DHCP handling.
            for rack_id in self.watching:
                try:
                    self.postgresListener.unregister(
                        "sys_dhcp_%s" % rack_id, self.dhcpHandler
                    )
                except PostgresListenerUnregistrationError:
                    # Error is acceptable as it might not have been called yet.
                    pass

            self.watching = set()
            self.needsDHCPUpdate = set()
            self.starting = None
            if self.processing.running:
                self.processing.stop()
                return self.processingDone

        if self.starting is None:
            return maybeDeferred(cleanUp)
        else:
            self.starting.cancel()
            self.starting.addBoth(callOut, cleanUp)
            return self.starting

    def coreHandler(self, channel, message):
        """Called when the `sys_core_{regiond_id}` message is received."""
        action, rack_id = message.split("_", 1)
        rack_id = int(rack_id)

        log.debug(
            "[pid:{pid()}] received {action} action for rack: {rack_id}",
            pid=os.getpid,
            action=action,
            rack_id=rack_id,
        )

        if action == "unwatch":
            if rack_id in self.watching:
                self.postgresListener.unregister(
                    "sys_dhcp_%s" % rack_id, self.dhcpHandler
                )
            else:
                log.warn(
                    "[pid:{pid()}] received unwatched when not watching "
                    "for rack: {rack_id}",
                    pid=os.getpid,
                    rack_id=rack_id,
                )
            self.needsDHCPUpdate.discard(rack_id)
            self.watching.discard(rack_id)
        elif action == "watch":
            if rack_id not in self.watching:
                self.postgresListener.register(
                    "sys_dhcp_%s" % rack_id, self.dhcpHandler
                )
            else:
                log.warn(
                    "[pid:{pid()}] received watched when already watching "
                    "for rack: {rack_id}",
                    pid=os.getpid,
                    rack_id=rack_id,
                )
            self.watching.add(rack_id)
            self.needsDHCPUpdate.add(rack_id)
            self.startProcessing()
        else:
            raise ValueError("Unknown action: %s." % action)

        log.debug(
            "[pid:{pid()}] currently watching racks: {racks()}",
            pid=os.getpid,
            racks=lambda: ", ".join(
                [str(rack_id) for rack_id in self.watching]
            ),
        )
        log.debug(
            "[pid:{pid()}] racks requiring DHCP push: {racks()}",
            pid=os.getpid,
            racks=lambda: ", ".join(
                [str(rack_id) for rack_id in self.needsDHCPUpdate]
            ),
        )

    def dhcpHandler(self, channel, message):
        """Called when the `sys_dhcp_{rackd_id}` message is received."""
        _, rack_id = channel.split("sys_dhcp_")
        rack_id = int(rack_id)
        if rack_id in self.watching:
            self.needsDHCPUpdate.add(rack_id)
            self.startProcessing()

            log.debug(
                "[pid:{pid()}] racks requiring DHCP push: {racks()}",
                pid=os.getpid,
                racks=lambda: ", ".join(
                    [str(rack_id) for rack_id in self.needsDHCPUpdate]
                ),
            )
        else:
            log.warn(
                "[pid:{pid()}] received DHCP push notify when not watching "
                "for rack: {rack_id}",
                pid=os.getpid,
                rack_id=rack_id,
            )

    def startProcessing(self):
        """Start the process looping call."""
        if not self.processing.running:
            self.processingDone = self.processing.start(
                self.PROCESSING_DELAY, now=False
            )

    def process(self):
        """Process the next rack controller that needs an update."""
        if not self.running:
            # We're shutting down.
            self.processing.stop()
        elif len(self.needsDHCPUpdate) == 0:
            # Nothing more to do.
            self.processing.stop()
        else:

            def _retryOnFailure(failure, rack_id):
                self.needsDHCPUpdate.add(rack_id)
                return failure

            rack_id = self.needsDHCPUpdate.pop()
            d = maybeDeferred(self.processDHCP, rack_id)
            d.addErrback(_retryOnFailure, rack_id)
            d.addErrback(lambda f: f.trap(NoConnectionsAvailable))
            d.addErrback(
                log.err,
                "Failed configuring DHCP on rack controller 'id:%d'."
                % rack_id,
            )
            return d

    def processDHCP(self, rack_id):
        """Process DHCP for the rack controller."""
        log.debug(
            "[pid:{pid()}] pushing DHCP to rack: {rack_id}",
            pid=os.getpid,
            rack_id=rack_id,
        )

        def unwatch_if_does_not_exist(f):
            """Un-watches the rack when RackController no longer exists in the DB"""
            # Only handle DoesNotExist for RackController, re-raise other errors
            f.trap(RackController.DoesNotExist)
            if rack_id in self.watching:
                log.info(
                    f"[pid:{os.getpid()}] watched rack is not in the DB, un-watching: {rack_id}"
                )
                # Note: since proper unwatch message might come later, "received unwatched when not watching"
                # warning might show up.
                self.watching.discard(rack_id)
            else:
                # Might happen when unwatch message was processed after configure_dhcp was called but before it failed
                log.info(
                    f"[pid:{os.getpid()}] DHCP configuration push failed as rack is not in the DB: {rack_id}"
                )

        d = deferToDatabase(
            transactional(RackController.objects.get), id=rack_id
        )
        d.addCallback(dhcp.configure_dhcp)
        d.addErrback(unwatch_if_does_not_exist)
        return d
