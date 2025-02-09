# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP probing service."""

from datetime import timedelta

from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks, maybeDeferred
from twisted.internet.threads import deferToThread
from twisted.protocols.amp import UnhandledCommand

from provisioningserver.config import is_dev_environment
from provisioningserver.dhcp.detect import probe_interface
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import ReportForeignDHCPServer
from provisioningserver.utils.network import (
    get_all_interfaces_definition,
    has_ipv4_address,
)
from provisioningserver.utils.twisted import pause, retries

maaslog = get_maas_logger("dhcp.probe")
log = LegacyLogger()


class DHCPProbeService(TimerService):
    """Service to probe for DHCP servers on the rack controller interface's.

    Built on top of Twisted's `TimerService`.

    :param reactor: An `IReactor` instance.
    """

    check_interval = timedelta(minutes=10).total_seconds()

    def __init__(self, client_service, reactor):
        # Call self.try_probe_dhcp() every self.check_interval.
        super().__init__(self.check_interval, self.try_probe_dhcp)
        self.clock = reactor
        self.client_service = client_service

    def log(self, *args, **kwargs):
        log.msg(*args, **kwargs, system=type(self).__name__)

    def err(self, *args, **kwargs):
        log.err(*args, **kwargs, system=type(self).__name__)

    def _get_interfaces(self):
        """Return the interfaces for this rack controller."""
        d = deferToThread(get_all_interfaces_definition)
        d.addCallback(
            lambda interfaces: [
                name
                for name, info in interfaces.items()
                # No IPv4 address (unfortunately) means that MAAS cannot probe
                # this interface. This is because ultimately the DHCP probe
                # mechanism must send out a unicast UDP packet from the
                # interface in order to receive a response, and the TCP/IP
                # stack will drop packets coming back from the server if an
                # unexpected address is used.
                if info["enabled"] and has_ipv4_address(info)
            ]
        )
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
                "method."
            )

        d = client(
            ReportForeignDHCPServer,
            system_id=client.localIdent,
            interface_name=name,
            dhcp_ip=dhcp_ip,
        )
        d.addErrback(eb_unhandled)
        return d

    @inlineCallbacks
    def _tryGetClient(self):
        client = None
        for elapsed, remaining, wait in retries(15, 5, self.clock):  # noqa: B007
            try:
                client = yield self.client_service.getClientNow()
                break
            except NoConnectionsAvailable:
                yield pause(wait, self.clock)
        return client

    @inlineCallbacks
    def probe_dhcp(self):
        """Find all the interfaces on this rack controller and probe for
        DHCP servers.
        """
        client = yield self._tryGetClient()
        if client is None:
            maaslog.error(
                "Can't initiate DHCP probe; no RPC connection to region."
            )
            return

        # Iterate over interfaces and probe each one.
        interfaces = yield self._get_interfaces()
        self.log(
            "Probe for external DHCP servers started on interfaces: %s."
            % (", ".join(interfaces))
        )
        for interface in interfaces:
            try:
                servers = yield maybeDeferred(probe_interface, interface)
            except OSError as e:
                error = (
                    "Failed to probe for external DHCP servers on interface "
                    "'%s'." % interface
                )
                if is_dev_environment():
                    error += " (Did you configure authbind per HACKING.rst?)"
                self.err(e, error)
                continue
            else:
                if len(servers) > 0:
                    # XXX For now, only send the region one server, since
                    # it can only track one per VLAN (this could be considered
                    # a bug).
                    yield self._inform_region_of_dhcp(
                        client, interface, servers.pop()
                    )
                else:
                    yield self._inform_region_of_dhcp(client, interface, None)
        self.log("External DHCP probe complete.")

    @inlineCallbacks
    def try_probe_dhcp(self):
        log.debug("Running periodic DHCP probe.")
        try:
            yield self.probe_dhcp()
        except Exception as error:
            maaslog.error("Unable to probe for DHCP servers: %s", str(error))
            self.err(error, "Unable to probe for DHCP servers.")
        else:
            log.debug("Finished periodic DHCP probe.")
