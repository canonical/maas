# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS service for the rack controller."""

__all__ = [
    "RackDNSService",
]

from collections import defaultdict
from datetime import timedelta

import attr
from netaddr import IPAddress
from provisioningserver.dns.actions import (
    bind_reload_with_retries,
    bind_write_configuration,
    bind_write_options,
)
from provisioningserver.logger import LegacyLogger
from provisioningserver.rpc import exceptions
from provisioningserver.rpc.region import (
    GetControllerType,
    GetDNSConfiguration,
)
from provisioningserver.utils.twisted import callOut
from twisted.application.internet import TimerService
from twisted.internet.defer import (
    inlineCallbacks,
    maybeDeferred,
)
from twisted.internet.threads import deferToThread


log = LegacyLogger()


class RackDNSService(TimerService):

    # Initial start the interval is low so that forwarders of bind9 gets
    # at least one region controller. When no region controllers are set
    # on the forwarders the interval is always set to the lower setting.
    INTERVAL_LOW = timedelta(seconds=5).total_seconds()

    # Once at least one region controller is set on the forwarders then
    # the inverval is higher as at least one controller is handling the
    # DNS requests.
    INTERVAL_HIGH = timedelta(seconds=30).total_seconds()

    _configuration = None
    _rpc_service = None

    def __init__(self, rpc_service, reactor):
        super().__init__(self.INTERVAL_LOW, self._tryUpdate)
        self._rpc_service = rpc_service
        self.clock = reactor

    def _update_interval(self, num_region_ips):
        """Change the update interval."""
        if num_region_ips <= 0:
            self._loop.interval = self.step = self.INTERVAL_LOW
        else:
            self._loop.interval = self.step = self.INTERVAL_HIGH

    def _tryUpdate(self):
        """Update the NTP server running on this host."""
        d = maybeDeferred(self._getConfiguration)
        d.addCallback(self._maybeApplyConfiguration)
        d.addErrback(self._updateFailed)
        return d

    def _updateFailed(self, failure):
        """Top-level error handler for the periodic task."""
        if failure.check(exceptions.NoSuchNode):
            pass  # This node is not yet recognised by the region.
        elif failure.check(exceptions.NoConnectionsAvailable):
            pass  # The region is not yet available.
        else:
            log.err(failure, "Failed to update DNS configuration.")

    def _genRegionIps(self):
        """Generate IP addresses for all region controllers this rack
        controller is connected to."""
        # Filter the connects by region.
        conn_per_region = defaultdict(set)
        for eventloop, connection in self._rpc_service.connections.items():
            conn_per_region[eventloop.split(':')[0]].add(connection)
        for _, connections in conn_per_region.items():
            # Sort the connections so the same IP is always picked per
            # region controller. This ensures that the HTTP configuration
            # is not reloaded unless its actually required to reload.
            conn = list(sorted(
                connections, key=lambda conn: conn.address[0]))[0]
            addr = IPAddress(conn.address[0])
            if addr.is_ipv4_mapped():
                yield str(addr.ipv4())
            else:
                yield str(addr)

    @inlineCallbacks
    def _getConfiguration(self):
        """Return DNS server configuration.

        The configuration object returned is comparable with previous and
        subsequently obtained configuration objects, allowing this service to
        determine whether a change needs to be applied to the DNS server.
        """
        client = yield self._rpc_service.getClientNow()
        dns_configuation = yield client(
            GetDNSConfiguration, system_id=client.localIdent)
        controller_type = yield client(
            GetControllerType, system_id=client.localIdent)
        region_ips = list(self._genRegionIps())
        self._update_interval(len(region_ips))
        return _Configuration(
            upstream_dns=region_ips,
            trusted_networks=dns_configuation["trusted_networks"],
            is_region=controller_type["is_region"],
            is_rack=controller_type["is_rack"])

    def _maybeApplyConfiguration(self, configuration):
        """Reconfigure the DNS server if the configuration changes.

        Reconfigure and restart `bind9` if the current configuration differs
        from a previously applied configuration, otherwise do nothing.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        if configuration != self._configuration:
            d = maybeDeferred(self._applyConfiguration, configuration)
            d.addCallback(callOut, self._configurationApplied, configuration)
            return d

    def _applyConfiguration(self, configuration):
        """Configure the DNS server.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        if configuration.is_rack and not configuration.is_region:
            d = deferToThread(
                self._configure,
                configuration.upstream_dns,
                configuration.trusted_networks)
            return d

    def _configurationApplied(self, configuration):
        """Record the currently applied DNS server configuration.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        self._configuration = configuration

    def _configure(self, upstream_dns, trusted_networks):
        """Update the DNS configuration for the rack.

        Possible node was converted from a region to a rack-only, so we always
        ensure that all zones are removed.
        """
        # We allow the region controller to do the dnssec validation, if
        # enabled. On the rack controller we just let it pass through.
        bind_write_options(
            upstream_dns=list(sorted(upstream_dns)), dnssec_validation='no')

        # No zones on the rack controller.
        bind_write_configuration([], list(sorted(trusted_networks)))

        # Reloading with retries to ensure that it actually works.
        bind_reload_with_retries()


@attr.s
class _Configuration:
    """Configuration for the rack's DNS server."""

    # Addresses of upstream dns servers.
    upstream_dns = attr.ib(converter=frozenset)
    # Trusted networks.
    trusted_networks = attr.ib(converter=frozenset)

    # The type of this controller. It's fair to assume that is_rack is true,
    # but check nevertheless before applying this configuration.
    is_region = attr.ib(converter=bool)
    is_rack = attr.ib(converter=bool)
