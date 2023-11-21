# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""External service for the rack controller.

Managers all the external services that the rack controller runs.
"""


from abc import ABCMeta, abstractmethod, abstractproperty
from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlparse

import attr
from netaddr import IPAddress
from twisted.application.internet import TimerService
from twisted.internet.defer import DeferredList, inlineCallbacks, maybeDeferred
from twisted.internet.threads import deferToThread

from provisioningserver.agent import config as agent_config
from provisioningserver.config import ClusterConfiguration
from provisioningserver.dns.actions import (
    bind_reload_with_retries,
    bind_write_configuration,
    bind_write_options,
)
from provisioningserver.logger import LegacyLogger
from provisioningserver.ntp.config import configure_rack
from provisioningserver.proxy import config as proxy_config
from provisioningserver.rpc import exceptions
from provisioningserver.rpc.region import (
    GetControllerType,
    GetDNSConfiguration,
    GetProxyConfiguration,
    GetSyslogConfiguration,
    GetTimeConfiguration,
)
from provisioningserver.service_monitor import service_monitor
from provisioningserver.syslog import config as syslog_config
from provisioningserver.utils import snap
from provisioningserver.utils.env import MAAS_ID, MAAS_SHARED_SECRET, MAAS_UUID
from provisioningserver.utils.twisted import callOut, callOutToThread

log = LegacyLogger()


class RackOnlyExternalService(metaclass=ABCMeta):
    """Service that should only run when it rack-only mode."""

    _configuration = None

    @abstractproperty
    def service_name(self):
        """Name of the service in `service_monitor`."""

    @abstractmethod
    def _configure(self):
        """Configure the service."""

    def _genRegionIps(
        self, connections, bracket_ipv6=False, include_name=False
    ):
        """Generate IP addresses for all region controllers this rack
        controller is connected to."""

        def _getNameFromEventloop(eventloop):
            if ":" in eventloop:
                return eventloop.split(":", 1)[0]
            else:
                return eventloop

        # Filter the connects by region.
        conn_per_region = defaultdict(set)
        for eventloop, connection_set in connections.items():
            for connection in connection_set:
                conn_per_region[eventloop.split(":")[0]].add(connection)
        for eventloop, connections in conn_per_region.items():
            # Sort the connections so the same IP is always picked per
            # region controller. This ensures that the HTTP configuration
            # is not reloaded unless its actually required to reload.
            conn = list(sorted(connections, key=lambda conn: conn.address[0]))[
                0
            ]
            addr = IPAddress(conn.address[0])
            if addr.is_ipv4_mapped():
                addr = str(addr.ipv4())
            elif addr.version == 6 and bracket_ipv6:
                addr = "[%s]" % addr
            else:
                addr = str(addr)
            if include_name:
                yield (_getNameFromEventloop(eventloop), addr)
            else:
                yield addr

    def _maybeApplyConfiguration(self, configuration):
        """Reconfigure the external server if the configuration changes.

        :param configuration: The configuration object.
        """
        if configuration != self._configuration:
            d = maybeDeferred(self._applyConfiguration, configuration)
            d.addCallback(callOut, self._configurationApplied, configuration)
            return d

    def _applyConfiguration(self, configuration):
        """Configure the external server.

        :param configuration: The configuration object.
        """
        service = service_monitor.getServiceByName(self.service_name)
        if configuration.is_rack and not configuration.is_region:
            # Service is managed by the rack controller, so the service
            # should be on.
            service.on()
            return maybeDeferred(self._configure, configuration)
        else:
            # Service should not be managed by the rack controller. The region
            # controller manages this service.
            service.any("managed by the region")

    def _configurationApplied(self, configuration):
        """Record the currently applied external server configuration.

        :param configuration: The configuration object.
        """
        self._configuration = configuration


class RackNTP(RackOnlyExternalService):
    """External NTP service ran only in rack-only mode."""

    service_name = "ntp_rack"

    def _tryUpdate(self, config):
        """Update the NTP server running on this host."""
        d = maybeDeferred(
            self._getConfiguration,
            config.controller_type,
            config.time_configuration,
        )
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
            is_rack=controller_type["is_rack"],
        )

    def _configure(self, configuration):
        """Configure the NTP server.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        d = deferToThread(
            configure_rack, configuration.references, configuration.peers
        )
        d.addCallback(callOut, service_monitor.restartService, "ntp_rack")
        return d


class RackDNS(RackOnlyExternalService):
    """External DNS service ran only in rack-only mode."""

    service_name = "dns_rack"

    def _tryUpdate(self, config):
        """Update the NTP server running on this host."""
        d = maybeDeferred(
            self._getConfiguration,
            config.controller_type,
            config.dns_configuration,
            config.connections,
        )
        d.addCallback(self._maybeApplyConfiguration)
        return d

    def _getConfiguration(
        self, controller_type, dns_configuration, connections
    ):
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
            is_rack=controller_type["is_rack"],
        )

    def _bindConfigure(self, configuration):
        """Update the DNS configuration for the rack.

        Possible node was converted from a region to a rack-only, so we always
        ensure that all zones are removed.
        """
        # We allow the region controller to do the dnssec validation, if
        # enabled. On the rack controller we just let it pass through.
        bind_write_options(
            upstream_dns=list(sorted(configuration.upstream_dns)),
            dnssec_validation="no",
        )

        # No zones on the rack controller.
        bind_write_configuration(
            [], list(sorted(configuration.trusted_networks))
        )

    def _bindReload(self):
        """Reload bind for the rack controller."""
        # Reloading with retries to ensure that it actually works.
        bind_reload_with_retries()

    def _configure(self, configuration):
        """Configure the DNS server.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        d = deferToThread(self._bindConfigure, configuration)
        d.addCallback(
            callOut, service_monitor.ensureService, self.service_name
        )
        d.addCallback(callOutToThread, self._bindReload)
        return d


class RackProxy(RackOnlyExternalService):
    """External proxy service ran only in rack-only mode."""

    service_name = "proxy_rack"

    def _tryUpdate(self, config):
        """Update the proxy server running on this host."""
        d = maybeDeferred(
            self._getConfiguration,
            config.controller_type,
            config.proxy_configuration,
            config.connections,
        )
        d.addCallback(self._maybeApplyConfiguration)
        return d

    def _getConfiguration(
        self, controller_type, proxy_configuration, connections
    ):
        """Return proxy server configuration.

        The configuration object returned is comparable with previous and
        subsequently obtained configuration objects, allowing this service to
        determine whether a change needs to be applied to the proxy server.
        """
        region_ips = list(self._genRegionIps(connections, bracket_ipv6=True))
        return _ProxyConfiguration(
            enabled=proxy_configuration["enabled"],
            port=proxy_configuration["port"],
            allowed_cidrs=proxy_configuration["allowed_cidrs"],
            prefer_v4_proxy=proxy_configuration["prefer_v4_proxy"],
            upstream_proxies=region_ips,
            is_region=controller_type["is_region"],
            is_rack=controller_type["is_rack"],
        )

    def _applyConfiguration(self, configuration):
        """Configure the proxy server.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        service = service_monitor.getServiceByName(self.service_name)
        if configuration.is_rack and not configuration.is_region:
            if not configuration.enabled:
                # Proxy should be off and remain off.
                service.off("not enabled")
                return service_monitor.ensureService(self.service_name)

            # Proxy enabled; configure it.
            d = deferToThread(self._configure, configuration)
            # Ensure that the service is on.
            service.on()
            if snap.running_in_snap():
                # XXX: andreserl 2016-05-09 bug=1687620. When running in a
                # snap, supervisord tracks services. It does not support
                # reloading. Instead, we need to restart the service.
                d.addCallback(
                    callOut, service_monitor.restartService, self.service_name
                )
            else:
                d.addCallback(
                    callOut, service_monitor.reloadService, self.service_name
                )
            return d
        else:
            # Proxy is managed by the region.
            service.any("managed by the region")

    def _configure(self, configuration):
        """Update the proxy configuration for the rack."""
        peers = sorted(
            f"http://{upstream}:{configuration.port}"
            for upstream in configuration.upstream_proxies
        )
        proxy_config.write_config(
            configuration.allowed_cidrs,
            peer_proxies=peers,
            prefer_v4_proxy=configuration.prefer_v4_proxy,
            maas_proxy_port=configuration.port,
        )


class RackSyslog(RackOnlyExternalService):
    """External syslog service ran only in rack-only mode."""

    service_name = "syslog_rack"

    def _tryUpdate(self, config):
        """Update the syslog server running on this host."""
        d = maybeDeferred(
            self._getConfiguration,
            config.controller_type,
            config.syslog_configuration,
            config.connections,
        )
        d.addCallback(self._maybeApplyConfiguration)
        return d

    def _getConfiguration(
        self, controller_type, syslog_configuration, connections
    ):
        """Return syslog server configuration.

        The configuration object returned is comparable with previous and
        subsequently obtained configuration objects, allowing this service to
        determine whether a change needs to be applied to the syslog server.
        """
        forwarders = list(
            self._genRegionIps(
                connections, bracket_ipv6=True, include_name=True
            )
        )
        return _SyslogConfiguration(
            port=syslog_configuration["port"],
            forwarders=forwarders,
            is_region=controller_type["is_region"],
            is_rack=controller_type["is_rack"],
            promtail_port=syslog_configuration["promtail_port"],
        )

    def _applyConfiguration(self, configuration):
        """Configure the proxy server.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        service = service_monitor.getServiceByName(self.service_name)
        if configuration.is_rack and not configuration.is_region:
            service.on()
            d = deferToThread(self._configure, configuration)
            d.addCallback(
                callOut, service_monitor.restartService, self.service_name
            )
            return d
        else:
            # Proxy is managed by the region.
            service.any("managed by the region")

    def _configure(self, configuration):
        """Update the syslog configuration for the rack."""
        # Convert the frozenset to a dictionary before constructing the
        # dictionary that `syslog_config.write_config` expects. This ensures
        # that only unique regions are included in the forwarders.
        forwarders = [
            {"name": name, "ip": ip}
            for name, ip in dict(configuration.forwarders).items()
        ]
        syslog_config.write_config(
            False,
            forwarders=forwarders,
            port=configuration.port,
            promtail_port=configuration.promtail_port,
        )


class RackAgent(RackOnlyExternalService):
    """External maas-agent service"""

    service_name = "agent"

    def _configure(self):
        controllers = []
        with ClusterConfiguration.open() as config:
            controllers = [urlparse(url).hostname for url in config.maas_url]
            debug_enabled = config.debug

        config = agent_config.Configuration(
            maas_uuid=MAAS_UUID.get(),
            system_id=MAAS_ID.get(),
            secret=MAAS_SHARED_SECRET.get(),
            controllers=controllers,
            log_level="debug" if debug_enabled else "info",
        )

        agent_config.write_config(config)

    def _tryUpdate(self, config):
        d = deferToThread(self._configure)
        d.addCallback(
            callOut, service_monitor.restartService, self.service_name
        )
        return d


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
                ("NTP", RackNTP()),
                ("DNS", RackDNS()),
                ("proxy", RackProxy()),
                ("syslog", RackSyslog()),
                ("agent", RackAgent()),
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
            GetControllerType, system_id=client.localIdent
        )
        time_configuration = yield client(
            GetTimeConfiguration, system_id=client.localIdent
        )
        dns_configuration = yield client(
            GetDNSConfiguration, system_id=client.localIdent
        )
        proxy_configuration = yield client(
            GetProxyConfiguration, system_id=client.localIdent
        )
        syslog_configuration = yield client(
            GetSyslogConfiguration, system_id=client.localIdent
        )
        return _Configuration(
            controller_type=controller_type,
            time_configuration=time_configuration,
            dns_configuration=dns_configuration,
            proxy_configuration=proxy_configuration,
            syslog_configuration=syslog_configuration,
            connections=self._rpc_service.connections,
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
        except Exception:
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

    # Proxy configuration for the controller.
    proxy_configuration = attr.ib(converter=dict)

    # Syslog configuration for the controller.
    syslog_configuration = attr.ib(converter=dict)

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


@attr.s
class _ProxyConfiguration:
    """Configuration for the rack's proxy server."""

    # Proxy enabled.
    enabled = attr.ib(converter=bool)

    # Port to run proxy on.
    port = attr.ib(converter=int)

    # Allowed CIDRs for the proxy.
    allowed_cidrs = attr.ib(converter=frozenset)

    # Prefer IPv4 over IPv6.
    prefer_v4_proxy = attr.ib(converter=bool)

    # Addresses of upstream proxy servers.
    upstream_proxies = attr.ib(converter=frozenset)

    # The type of this controller. It's fair to assume that is_rack is true,
    # but check nevertheless before applying this configuration.
    is_region = attr.ib(converter=bool)
    is_rack = attr.ib(converter=bool)


def converter_obj(expected):
    """Convert the given value to an object of type `expected`."""

    def converter(value):
        if value is None:
            return None
        if isinstance(value, expected):
            return value
        else:
            raise TypeError(f"{value!r} is not of type {expected}")

    return converter


@attr.s
class _SyslogConfiguration:
    """Configuration for the rack's syslog server."""

    # Port to run syslog on.
    port = attr.ib(converter=int)

    # Forwards to send the logs to.
    forwarders = attr.ib(converter=frozenset)

    # The type of this controller. It's fair to assume that is_rack is true,
    # but check nevertheless before applying this configuration.
    is_region = attr.ib(converter=bool)
    is_rack = attr.ib(converter=bool)

    # forward logs to promtail
    promtail_port = attr.ib(converter=converter_obj(int), default=None)
