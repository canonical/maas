# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""NTP service for the region controller."""

__all__ = [
    "RegionNetworkTimeProtocolService",
]

from collections import defaultdict
from datetime import timedelta

import attr
from maasserver.models.config import Config
from maasserver.models.node import RegionController
from maasserver.routablepairs import find_addresses_between_nodes
from maasserver.service_monitor import service_monitor
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.ntp.config import configure_region
from provisioningserver.utils.text import split_string_list
from provisioningserver.utils.twisted import (
    callOut,
    synchronous,
)
from twisted.application.internet import TimerService
from twisted.internet.defer import maybeDeferred
from twisted.internet.threads import deferToThread
from twisted.python import log


class RegionNetworkTimeProtocolService(TimerService):

    interval = timedelta(seconds=30).total_seconds()

    _configuration = None

    def __init__(self, reactor):
        super().__init__(self.interval, self._tryUpdate)
        self.clock = reactor

    def _tryUpdate(self):
        """Update the NTP server running on this host."""
        d = deferToDatabase(self._getConfiguration)
        d.addCallback(self._maybeApplyConfiguration)
        d.addErrback(log.err, "Failed to update NTP configuration.")
        return d

    @synchronous
    @transactional
    def _getConfiguration(self):
        """Return NTP server configuration.

        The configuration object returned is comparable with previous and
        subsequently obtained configuration objects, allowing this service to
        determine whether a change needs to be applied to the NTP server.
        """
        return _Configuration(self._getReferences(), self._getPeers())

    @synchronous
    def _getReferences(self):
        """Return an immutable set of configured NTP servers."""
        ntp_servers = Config.objects.get_config("ntp_servers")
        return frozenset(split_string_list(ntp_servers))

    @synchronous
    def _getPeers(self):
        """Return an immutable set of peer IP addresses."""
        try:
            this_region = RegionController.objects.get_running_controller()
        except RegionController.DoesNotExist:
            return frozenset()  # Probably a transient error.
        else:
            peer_regions = RegionController.objects.exclude(id=this_region.id)
            peer_addresses = defaultdict(list)
            for _, _, peer_region, peer_address in (
                    find_addresses_between_nodes({this_region}, peer_regions)):
                peer_addresses[peer_region].append(peer_address)
            return frozenset(
                min(peer_addresses, key=self._peerAddressSortKey).format()
                for peer_addresses in peer_addresses.values())

    @staticmethod
    def _peerAddressSortKey(address):
        """A key that would sort IPv6 before IPv4, then address order."""
        return (0 if address.version == 6 else 1), address.value

    def _maybeApplyConfiguration(self, configuration):
        """Reconfigure the NTP server if the configuration changes.

        Reconfigure and restart `ntpd` if the current configuration differs
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
        d = deferToThread(
            configure_region, configuration.references, configuration.peers)
        d.addCallback(
            callOut, service_monitor.restartService, "ntp_region")
        return d

    def _configurationApplied(self, configuration):
        """Record the currently applied NTP server configuration.

        :param configuration: The configuration object obtained from
            `_getConfiguration`.
        """
        self._configuration = configuration


@attr.s
class _Configuration:
    """Configuration for the region's NTP servers."""

    # Addresses or hostnames of reference time servers.
    references = attr.ib(convert=frozenset)

    # Addresses of peer region controller hosts.
    peers = attr.ib(convert=frozenset)
