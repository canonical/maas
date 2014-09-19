# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Periodic DHCP probing service."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "PeriodicDHCPProbeService",
    ]


from datetime import timedelta
import socket

from provisioningserver.dhcp.detect import probe_interface
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import (
    GetClusterInterfaces,
    ReportForeignDHCPServer,
    )
from provisioningserver.utils.twisted import (
    pause,
    retries,
    )
from twisted.application.internet import TimerService
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )
from twisted.internet.threads import deferToThread
from twisted.protocols.amp import UnhandledCommand


maaslog = get_maas_logger("dhcp.probe")


class PeriodicDHCPProbeService(TimerService, object):
    """Service to probe for DHCP servers on this cluster's network.

    Built on top of Twisted's `TimerService`.

    :param reactor: An `IReactor` instance.
    :param cluster_uuid: This cluster's UUID.
    """

    check_interval = timedelta(minutes=10).total_seconds()

    def __init__(self, client_service, reactor, cluster_uuid):
        # Call self.try_probe_dhcp() every self.check_interval.
        super(PeriodicDHCPProbeService, self).__init__(
            self.check_interval, self.try_probe_dhcp)
        self.clock = reactor
        self.uuid = cluster_uuid
        self.client_service = client_service

    @inlineCallbacks
    def _get_cluster_interfaces(self, client):
        """Return the interfaces for this cluster."""
        try:
            response = yield client(
                GetClusterInterfaces, cluster_uuid=self.uuid)
        except UnhandledCommand:
            # The region hasn't been upgraded to support this method
            # yet, so give up. Returning an empty dict means that this
            # run will end, since there are no interfaces to check.
            maaslog.error(
                "Unable to query region for interfaces: Region does not "
                "support the GetClusterInterfaces RPC method.")
            returnValue({})
        else:
            returnValue(response['interfaces'])

    @inlineCallbacks
    def _inform_region_of_foreign_dhcp(self, client, name,
                                       foreign_dhcp_ip):
        """Tell the region that there's a rogue DHCP server.

        :param client: The RPC client to use.
        :param name: The name of the network interface where the rogue
            DHCP server was found.
        :param foreign_dhcp_ip: The IP address of the rogue server.
        """
        try:
            yield client(
                ReportForeignDHCPServer, cluster_uuid=self.uuid,
                interface_name=name, foreign_dhcp_ip=foreign_dhcp_ip)
        except UnhandledCommand:
            # Not a lot we can do here... The region doesn't support
            # this method yet.
            maaslog.error(
                "Unable to inform region of rogue DHCP server: the region "
                "does not yet support the ReportForeignDHCPServer RPC "
                "method.")

    @inlineCallbacks
    def probe_dhcp(self):
        """Find all the interfaces on this cluster and probe for DHCP servers.
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

        cluster_interfaces = yield self._get_cluster_interfaces(client)
        # Iterate over interfaces and probe each one.
        for interface in cluster_interfaces:
            try:
                servers = yield deferToThread(
                    probe_interface, interface['interface'], interface['ip'])
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
                    yield self._inform_region_of_foreign_dhcp(
                        client, interface['name'], servers.pop())
                else:
                    yield self._inform_region_of_foreign_dhcp(
                        client, interface['name'], None)

    @inlineCallbacks
    def try_probe_dhcp(self):
        maaslog.debug("Running periodic DHCP probe.")
        try:
            yield self.probe_dhcp()
        except Exception as error:
            maaslog.error(
                "Unable to probe for rogue DHCP servers: %s",
                unicode(error))
        else:
            maaslog.debug("Finished periodic DHCP probe.")
