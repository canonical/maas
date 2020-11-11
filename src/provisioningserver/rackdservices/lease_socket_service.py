# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted service recieves lease information from the MAAS dhcpd.sock."""


from collections import deque
import json
import os

from twisted.application.service import Service
from twisted.internet import reactor, task
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import DatagramProtocol

from provisioningserver.logger import get_maas_logger
from provisioningserver.path import get_maas_data_path
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import UpdateLease
from provisioningserver.utils.twisted import pause, retries

maaslog = get_maas_logger("lease_socket_service")


def get_socket_path():
    """Return path to dhcpd.sock."""
    return get_maas_data_path("dhcpd.sock")


class LeaseSocketService(Service, DatagramProtocol):
    """Service for recieving lease information over MAAS dhcpd.sock."""

    # None, or a Deferred that will fire when the processor exits.
    done = None

    def __init__(self, client_service, reactor):
        self.client_service = client_service
        self.reactor = reactor
        self.address = get_socket_path()
        self.notifications = deque()
        self.processor = task.LoopingCall(
            self.processNotifications, clock=self.reactor
        )

    def startService(self):
        """Start the service."""
        super().startService()
        # Listen for packets from the `dhcpd.sock`.
        self.port = self.reactor.listenUNIXDatagram(self.address, self)

        # Start the looping call to handle received notifications.
        self.done = self.processor.start(0.1, now=False)

    def stopService(self):
        """Stop the service."""
        super().stopService()
        # Close the connection.
        self.port.connectionLost()
        del self.port

        # Remove the socket on the filesystem.
        os.remove(self.address)

        # Stop the processor once it has flushed all data.
        done, self.done = self.done, None
        self.processor.stop()
        return done

    def datagramReceived(self, data, conn):
        """Received packet of information.

        Packet should be JSON encode information about an updated lease.
        The packet is converted from JSON then placed in a queue to be sent to
        the region controller for processing.
        """
        # If this fails to convert, twisted will handle this gracefully and
        # not cause the reactor to crash.
        notification = json.loads(data.decode("utf-8"))

        # Place the notification into the list of notifications and the looping
        # call will handle sending the notification to the region. This ensures
        # that even if the connection is lost to the region that the queued
        # notifications will still be sent.
        self.notifications.append(notification)

    def processNotifications(self, clock=reactor):
        """Process all notifications."""

        def gen_notifications(notifications):
            while len(notifications) != 0:
                yield notifications.popleft()

        return task.coiterate(
            self.processNotification(notification, clock=clock)
            for notification in gen_notifications(self.notifications)
        )

    @inlineCallbacks
    def processNotification(self, notification, clock=reactor):
        """Send a notification to the region."""
        client = None
        for elapsed, remaining, wait in retries(30, 10, clock):
            try:
                client = yield self.client_service.getClientNow()
                break
            except NoConnectionsAvailable:
                yield pause(wait, self.clock)
        else:
            maaslog.error(
                "Can't send DHCP lease information, no RPC "
                "connection to region."
            )
            return

        # Notification contains all the required data except for the cluster
        # UUID. Add that into the notification and send the information to
        # the region for processing.
        notification["cluster_uuid"] = client.localIdent
        yield client(UpdateLease, **notification)
