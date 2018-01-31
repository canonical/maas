# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""NTP service for the rack controller."""

__all__ = [
    "RackNetworkTimeProtocolService",
]

from datetime import timedelta

import attr
from provisioningserver.logger import LegacyLogger
from provisioningserver.ntp.config import configure_rack
from provisioningserver.rpc import exceptions
from provisioningserver.rpc.region import (
    GetControllerType,
    GetTimeConfiguration,
)
from provisioningserver.service_monitor import service_monitor
from provisioningserver.utils.twisted import callOut
from twisted.application.internet import TimerService
from twisted.internet.defer import (
    inlineCallbacks,
    maybeDeferred,
)
from twisted.internet.threads import deferToThread


log = LegacyLogger()


class RackNetworkTimeProtocolService(TimerService):

    interval = timedelta(seconds=30).total_seconds()

    _configuration = None
    _rpc_service = None

    def __init__(self, rpc_service, reactor):
        super().__init__(self.interval, self._tryUpdate)
        self._rpc_service = rpc_service
        self.clock = reactor

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
            log.err(failure, "Failed to update NTP configuration.")

    @inlineCallbacks
    def _getConfiguration(self):
        """Return NTP server configuration.

        The configuration object returned is comparable with previous and
        subsequently obtained configuration objects, allowing this service to
        determine whether a change needs to be applied to the NTP server.
        """
        client = yield self._rpc_service.getClientNow()
        time_configuation = yield client(
            GetTimeConfiguration, system_id=client.localIdent)
        controller_type = yield client(
            GetControllerType, system_id=client.localIdent)
        return _Configuration(
            references=time_configuation["servers"],
            peers=time_configuation["peers"],
            is_region=controller_type["is_region"],
            is_rack=controller_type["is_rack"])

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


@attr.s
class _Configuration:
    """Configuration for the rack's NTP servers."""

    # Addresses or hostnames of reference time servers.
    references = attr.ib(converter=frozenset)
    # Addresses of peer time servers.
    peers = attr.ib(converter=frozenset)

    # The type of this controller. It's fair to assume that is_rack is true,
    # but check nevertheless before applying this configuration.
    is_region = attr.ib(converter=bool)
    is_rack = attr.ib(converter=bool)
