# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""NTP service for the region controller."""


from datetime import timedelta

import attr
from twisted.application.internet import TimerService
from twisted.internet.defer import maybeDeferred
from twisted.internet.threads import deferToThread

from maasserver import ntp
from maasserver.models.node import RegionController
from maasserver.service_monitor import service_monitor
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.ntp.config import configure_region
from provisioningserver.utils.twisted import callOut, synchronous

log = LegacyLogger()


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
        try:
            this_region = RegionController.objects.get_running_controller()
        except RegionController.DoesNotExist:
            # Treat this as a transient error.
            references = ntp.get_servers_for(None)
            peers = ntp.get_peers_for(None)
        else:
            references = ntp.get_servers_for(this_region)
            peers = ntp.get_peers_for(this_region)

        return _Configuration(references, peers)

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
        d = deferToThread(
            configure_region, configuration.references, configuration.peers
        )
        d.addCallback(callOut, service_monitor.restartService, "ntp_region")
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
    references = attr.ib(converter=frozenset)

    # Addresses of peer region controller hosts.
    peers = attr.ib(converter=frozenset)
