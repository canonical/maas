# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""External service for the rack controller.

Managers all the external services that the rack controller runs.
"""

__all__ = [
    "RackExternalService",
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
from provisioningserver.ntp.config import configure_rack
from provisioningserver.rpc import exceptions
from provisioningserver.rpc.region import (
    GetControllerType,
    GetDNSConfiguration,
    GetTimeConfiguration,
)
from provisioningserver.service_monitor import service_monitor
from provisioningserver.utils.twisted import callOut
from twisted.application.internet import TimerService
from twisted.internet.defer import (
    DeferredList,
    inlineCallbacks,
    maybeDeferred,
)
from twisted.internet.threads import deferToThread


log = LegacyLogger()


class RackNTP:

    _configuration = None

    def _tryUpdate(self, config):
        """Update the NTP server running on this host."""
        d = maybeDeferred(
            self._getConfiguration,
            config.controller_type,
            config.time_configuration)
        d.addCallback(self._maybeApplyConfiguration)
        return d

    def _getConfiguration(self, controller_type, time_configuration):
        """Return NTP server configuration.

        The configuration object returned is comparable with previous and
        subsequently obtained configuration objects, allowing this service to
        determine whether a change needs to be applied to the NTP server.
        """
        return _NTPConfiguration(
            references=time_configuration["servers"],
            peers=time_configuration["peers"],
            is_region=controller_type["is_region"],
            is_rack=controller_type["is_rack"])

    def _maybeApplyConfiguration(self, configuration):
        """Reconfigure the NTP server if the configuration changes.

        Reconfigure and restart `chrony` if the current configuration differs
        from a previously applied configuration, otherwise do nothing.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        if configuration != self._configuration:
            d = maybeDeferred(self._applyConfiguration, configuration)
            d.addCallback(callOut, self._configurationApplied, configuration)
            return d

    def _applyConfiguration(self, configuration):
        """Configure the NTP server.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        if configuration.is_rack and not configuration.is_region:
            d = deferToThread(
                configure_rack, configuration.references, configuration.peers)
            d.addCallback(callOut, service_monitor.restartService, "ntp_rack")
            return d

    def _configurationApplied(self, configuration):
        """Record the currently applied NTP server configuration.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        self._configuration = configuration


class RackDNS:

    _configuration = None

    def _tryUpdate(self, config):
        """Update the NTP server running on this host."""
        d = maybeDeferred(
            self._getConfiguration,
            config.controller_type,
            config.dns_configuration,
            config.connections)
        d.addCallback(self._maybeApplyConfiguration)
        return d

    def _genRegionIps(self, connections):
        """Generate IP addresses for all region controllers this rack
        controller is connected to."""
        # Filter the connects by region.
        conn_per_region = defaultdict(set)
        for eventloop, connection in connections.items():
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

    def _getConfiguration(
            self, controller_type, dns_configuration, connections):
        """Return DNS server configuration.

        The configuration object returned is comparable with previous and
        subsequently obtained configuration objects, allowing this service to
        determine whether a change needs to be applied to the DNS server.
        """
        region_ips = list(self._genRegionIps(connections))
        return _DNSConfiguration(
            upstream_dns=region_ips,
            trusted_networks=dns_configuration["trusted_networks"],
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


class RackExternalService(TimerService):

    # Initial start the interval is low so that forwarders of bind9 gets
    # at least one region controller. When no region controllers are set
    # on the forwarders the interval is always set to the lower setting.
    INTERVAL_LOW = timedelta(seconds=5).total_seconds()

    # Once at least one region controller is set on the forwarders then
    # the inverval is higher as at least one controller is handling the
    # DNS requests.
    INTERVAL_HIGH = timedelta(seconds=30).total_seconds()

    _rpc_service = None
    _services = None

    def __init__(self, rpc_service, reactor, services=None):
        super().__init__(self.INTERVAL_LOW, self._tryUpdate)
        self._rpc_service = rpc_service
        self.clock = reactor
        self._services = services
        if self._services is None:
            self._services = [
                ('NTP', RackNTP()),
                ('DNS', RackDNS()),
            ]

    def _update_interval(self, config):
        """Change the update interval."""
        if config is None or len(config.connections) == 0:
            self._loop.interval = self.step = self.INTERVAL_LOW
        else:
            self._loop.interval = self.step = self.INTERVAL_HIGH

    @inlineCallbacks
    def _getConfiguration(self):
        client = yield self._rpc_service.getClientNow()
        controller_type = yield client(
            GetControllerType, system_id=client.localIdent)
        time_configuration = yield client(
            GetTimeConfiguration, system_id=client.localIdent)
        dns_configuration = yield client(
            GetDNSConfiguration, system_id=client.localIdent)
        return _Configuration(
            controller_type=controller_type,
            time_configuration=time_configuration,
            dns_configuration=dns_configuration,
            connections=self._rpc_service.connections
        )

    @inlineCallbacks
    def _tryUpdate(self):
        """Update the NTP server running on this host."""
        try:
            config = yield self._getConfiguration()
        except exceptions.NoSuchNode:
            # This node is not yet recognised by the region.
            self._update_interval(None)
            return
        except exceptions.NoConnectionsAvailable:
            # The region is not yet available.
            self._update_interval(None)
            return
        except:
            log.err(None, "Failed to get external services configurations.")
            self._update_interval(None)
            return

        defers = []
        for name, service in self._services:
            d = maybeDeferred(service._tryUpdate, config)
            d.addErrback(log.err, "Failed to update %s configuration." % name)
            defers.append(d)
        yield DeferredList(defers)
        self._update_interval(config)


@attr.s
class _Configuration:
    """Configuration passed to the services."""

    # Type information for the controller.
    controller_type = attr.ib(converter=dict)

    # Time configuration for the controller.
    time_configuration = attr.ib(converter=dict)

    # DNS configuration for the controller.
    dns_configuration = attr.ib(converter=dict)

    # Current RPC connections for the controller.
    connections = attr.ib(converter=dict)


@attr.s
class _NTPConfiguration:
    """Configuration for the rack's NTP servers."""

    # Addresses or hostnames of reference time servers.
    references = attr.ib(converter=frozenset)
    # Addresses of peer time servers.
    peers = attr.ib(converter=frozenset)

    # The type of this controller. It's fair to assume that is_rack is true,
    # but check nevertheless before applying this configuration.
    is_region = attr.ib(converter=bool)
    is_rack = attr.ib(converter=bool)


@attr.s
class _DNSConfiguration:
    """Configuration for the rack's DNS server."""

    # Addresses of upstream dns servers.
    upstream_dns = attr.ib(converter=frozenset)
    # Trusted networks.
    trusted_networks = attr.ib(converter=frozenset)

    # The type of this controller. It's fair to assume that is_rack is true,
    # but check nevertheless before applying this configuration.
    is_region = attr.ib(converter=bool)
    is_rack = attr.ib(converter=bool)
