# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""" DHCP probing service."""

__all__ = [
    "DHCPProbeService",
    ]


from datetime import timedelta
import socket

from provisioningserver.dhcp.detect import probe_interface
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import ReportForeignDHCPServer
from provisioningserver.utils.network import get_all_interfaces_definition
from provisioningserver.utils.twisted import (
    pause,
    retries,
)
from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread
from twisted.protocols.amp import UnhandledCommand


maaslog = get_maas_logger("dhcp.probe")


class DHCPProbeService(TimerService, object):
    """Service to probe for DHCP servers on the rack controller interface's.

    Built on top of Twisted's `TimerService`.

    :param reactor: An `IReactor` instance.
    """

    check_interval = timedelta(minutes=10).total_seconds()

    def __init__(self, client_service, reactor):
        # Call self.try_probe_dhcp() every self.check_interval.
        super(DHCPProbeService, self).__init__(
            self.check_interval, self.try_probe_dhcp)
        self.clock = reactor
        self.client_service = client_service

    def _get_interfaces(self):
        """Return the interfaces for this rack controller."""
        d = deferToThread(get_all_interfaces_definition)
        d.addCallback(lambda interfaces: [
            name
            for name, info in interfaces.items()
            if info["enabled"]
        ])
        return d

    def _inform_region_of_dhcp(self, client, name, dhcp_ip):
        """Tell the region about the DHCP server.

        :param client: The RPC client to use.
        :param name: The name of the network interface where the rogue
            DHCP server was found.
        :param dhcp_ip: The IP address of the DHCP server.
        """

        def eb_unhandled(failure):
            failure.trap(UnhandledCommand)
            # Not a lot we can do here... The region doesn't support
            # this method yet.
            maaslog.error(
                "Unable to inform region of DHCP server: the region "
                "does not yet support the ReportForeignDHCPServer RPC "
                "method.")

        d = client(
            ReportForeignDHCPServer, system_id=client.localIdent,
            interface_name=name, dhcp_ip=dhcp_ip)
        d.addErrback(eb_unhandled)
        return d

    @inlineCallbacks
    def probe_dhcp(self):
        """Find all the interfaces on this rack controller and probe for
        DHCP servers.
        """
        client = None
        for elapsed, remaining, wait in retries(15, 5, self.clock):
            try:
                client = self.client_service.getClient()
                break
            except NoConnectionsAvailable:
                yield pause(wait, self.clock)
        else:
            maaslog.error(
                "Can't initiate DHCP probe, no RPC connection to region.")
            return

        # Iterate over interfaces and probe each one.
        interfaces = yield self._get_interfaces()
        for interface in interfaces:
            try:
                servers = yield deferToThread(probe_interface, interface)
            except socket.error:
                maaslog.error(
                    "Failed to probe sockets; did you configure authbind as "
                    "per HACKING.txt?")
                break
            else:
                if len(servers) > 0:
                    # Only send one, if it gets cleared out then the
                    # next detection pass will send a different one, if it
                    # still exists.
                    yield self._inform_region_of_dhcp(
                        client, interface, servers.pop())
                else:
                    yield self._inform_region_of_dhcp(
                        client, interface, None)

    @inlineCallbacks
    def try_probe_dhcp(self):
        maaslog.debug("Running periodic DHCP probe.")
        try:
            yield self.probe_dhcp()
        except Exception as error:
            maaslog.error(
                "Unable to probe for DHCP servers: %s",
                str(error))
        else:
            maaslog.debug("Finished periodic DHCP probe.")
