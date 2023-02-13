# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Syslog service for the region controller."""


from datetime import timedelta

import attr
from twisted.application.internet import TimerService
from twisted.internet.defer import maybeDeferred
from twisted.internet.threads import deferToThread

from maasserver.models.config import Config
from maasserver.models.node import RegionController
from maasserver.routablepairs import get_routable_address_map
from maasserver.service_monitor import service_monitor
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.syslog.config import write_config
from provisioningserver.utils.twisted import callOut, synchronous

log = LegacyLogger()


class RegionSyslogService(TimerService):
    interval = timedelta(seconds=30).total_seconds()

    _configuration = None

    def __init__(self, reactor):
        super().__init__(self.interval, self._tryUpdate)
        self.clock = reactor

    def _tryUpdate(self):
        """Update the syslog server running on this host."""
        d = deferToDatabase(self._getConfiguration)
        d.addCallback(self._maybeApplyConfiguration)
        d.addErrback(log.err, "Failed to update syslog configuration.")
        return d

    def _getPeers(self, region):
        """Return syslog peers to use for the given region."""
        peer_regions = RegionController.objects.exclude(id=region.id)
        peer_addresses_map = get_routable_address_map(peer_regions, region)
        return frozenset(
            (other_region.hostname, sorted(ip_addresses)[0])
            for other_region, ip_addresses in peer_addresses_map.items()
        )

    @synchronous
    @transactional
    def _getConfiguration(self):
        """Return syslog server configuration.

        The configuration object returned is comparable with previous and
        subsequently obtained configuration objects, allowing this service to
        determine whether a change needs to be applied to the syslog server.
        """
        try:
            this_region = RegionController.objects.get_running_controller()
        except RegionController.DoesNotExist:
            # Treat this as a transient error.
            peers = frozenset()
        else:
            if this_region.is_rack_controller:
                # Region controller is also a rack controller, need to forward
                # the received syslog message to the other region peers.
                peers = self._getPeers(this_region)
            else:
                # Only a region controller, no need to forward logs.
                peers = frozenset()

        port = Config.objects.get_config("maas_syslog_port")
        promtail_enabled = Config.objects.get_config("promtail_enabled")
        promtail_port = (
            Config.objects.get_config("promtail_port")
            if promtail_enabled
            else None
        )
        return _Configuration(port, peers, promtail_port)

    def _maybeApplyConfiguration(self, configuration):
        """Reconfigure the syslog server if the configuration changes.

        Reconfigure and restart `rsyslog` if the current configuration differs
        from a previously applied configuration, otherwise do nothing.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        if configuration != self._configuration:
            d = maybeDeferred(self._applyConfiguration, configuration)
            d.addCallback(callOut, self._configurationApplied, configuration)
            return d

    def _formatIP(self, addr):
        """Format the IP address into the format required by `rsyslog`."""
        if addr.is_ipv4_mapped():
            return str(addr.ipv4())
        elif addr.version == 6:
            return "[%s]" % addr
        else:
            return str(addr)

    def _applyConfiguration(self, configuration):
        """Configure the syslog server.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        d = deferToThread(
            write_config,
            True,
            [
                {"ip": self._formatIP(ip), "name": hostname}
                for hostname, ip in configuration.peers
            ],
            port=configuration.port,
            promtail_port=configuration.promtail_port,
        )
        d.addCallback(callOut, service_monitor.restartService, "syslog_region")
        return d

    def _configurationApplied(self, configuration):
        """Record the currently applied syslog server configuration.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        self._configuration = configuration


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
class _Configuration:
    """Configuration for the region's syslog servers."""

    # Port syslog binds to.
    port = attr.ib(converter=int)

    # Addresses of peer region controller hosts.
    peers = attr.ib(converter=frozenset)

    # Promtail syslog port
    promtail_port = attr.ib(converter=converter_obj(int), default=None)
