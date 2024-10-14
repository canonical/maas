# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service that periodically runs neighbour discovery scans on each rack."""

from datetime import timedelta

from django.utils import timezone
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, maybeDeferred

from maasserver import locks
from maasserver.api.discoveries import (
    get_scan_result_string_for_humans,
    scan_all_rack_networks,
)
from maasserver.models import Config, Subnet
from maasserver.utils.dblocks import DatabaseLockNotHeld
from maasserver.utils.orm import transactional, with_connection
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger

log = LegacyLogger()


# The check interval serves as somewhat of a throttle; normally, we will
# not scan more than once every CHECK_INTERVAL seconds (unless the discovery
# interval changes, and it's time to scan again).
CHECK_INTERVAL = timedelta(minutes=5).total_seconds()


class _InvalidScanState(Exception):
    """Raised when a scan was attempted, but should not have been allowed."""


class ActiveDiscoveryService(TimerService):
    """Service to actively scan for racks' network neighbours."""

    def __init__(self, clock=reactor, postgresListener=None):
        super().__init__(CHECK_INTERVAL, self.run)
        self.clock = clock
        self.listener = postgresListener
        self.discovery_enabled = None
        self.discovery_interval = None
        self.discovery_last_scan = None

    def startService(self):
        super().startService()
        if self.listener is not None:
            self.listener.register("config", self.refreshDiscoveryConfig)

    def stopService(self):
        if self.listener is not None:
            self.listener.unregister("config", self.refreshDiscoveryConfig)
        return super().stopService()

    @inlineCallbacks
    def refreshDiscoveryConfig(self, action=None, obj_id=None):
        """Reconfigures the discovery interval based on the global setting.

        Called when the postgresListener indicates that a configuration value
        has changed, and the first time the timer fires (immediately after
        the service starts).

        Prints log messages for significant configuration changes.
        """
        enabled, interval, last_scan = yield deferToDatabase(
            self.get_active_discovery_config
        )
        enabled_changed = enabled != self.discovery_enabled
        interval_changed = interval != self.discovery_interval
        last_scan_time_changed = last_scan != self.discovery_last_scan
        # If a significant configuration change occurred, log it.
        if enabled and interval_changed:
            log.msg(
                "Active network discovery: Discovery interval set to %d "
                "seconds." % interval
            )
        elif not enabled and enabled_changed:
            log.msg(
                "Active network discovery: periodic discovery is disabled."
            )
        self.discovery_enabled = enabled
        self.discovery_interval = interval
        self.discovery_last_scan = last_scan
        # Fire the scan timer now if the settings changed. The new settings
        # might mean it's time to scan now.
        if enabled and (interval_changed or last_scan_time_changed):
            yield self.run()

    @transactional
    def get_active_discovery_config(self):
        """Returns the current discovery configuration.

        The configuration is returned in the format:
            (enabled, interval, last_scan)

        Intended to be called with `deferToDatabase()`.
        """
        interval = Config.objects.get_config("active_discovery_interval")
        last_scan = Config.objects.get_config("active_discovery_last_scan")
        try:
            interval = int(interval)
        except ValueError:
            interval = 0
        try:
            last_scan = int(last_scan)
        except ValueError:
            last_scan = 0
        if interval <= 0:
            enabled = False
        else:
            enabled = True
        return enabled, interval, last_scan

    @transactional
    def get_cidrs_and_validate_scan_config(self):
        """Checks if all scan preconditions are met.

        Must only be called from `try_lock_and_scan()`, to be sure the database
        lock has been acquired.

        :raises: _InvalidScanState with human readable string as the error
            message, if the scan could not be performed.
        :return: list of `IPNetwork` objects to scan.
        """
        # Note: if passive discovery isn't enabled, there is no point in
        # doing active scanning. (MAAS will not see the results of the active
        # scan if it isn't listening for them.)
        discovery_config = Config.objects.get_network_discovery_config()
        if discovery_config.passive is False:
            raise _InvalidScanState(
                "Passive discovery is disabled. Skipping periodic scan."
            )
        # Check the discovery configuration one more time, just in case it
        # changed while we weren't holding the lock.
        enabled, interval, last_scan = self.get_active_discovery_config()
        if not enabled:
            raise _InvalidScanState(
                "Skipping active scan. Periodic discovery is now disabled."
            )
        current_time = self.getCurrentTimestamp()
        if (last_scan + interval) > current_time:
            raise _InvalidScanState(
                "Another region controller is already scanning. "
                "Skipping scan."
            )
        cidrs = Subnet.objects.get_cidr_list_for_periodic_active_scan()
        return cidrs

    @transactional
    def _update_last_scan_time(self):
        """Helper function to update the last_scan time in a transaction."""
        current_time = self.getCurrentTimestamp()
        Config.objects.set_config("active_discovery_last_scan", current_time)

    def scan_all_subnets(self, cidrs):
        """Scans the specified list of subnet CIDRs.

        Updates the last_scan time if a scan was initiated.

        :return: human readable string indicating scan results.
        """
        assert len(cidrs) != 0
        scan_results = scan_all_rack_networks(cidrs=cidrs)
        # Don't increment the last_scan value if we couldn't contact any
        # rack controllers to initiate the scan.
        if len(scan_results.available) > 0:
            self._update_last_scan_time()
        return get_scan_result_string_for_humans(scan_results)

    @with_connection
    def try_lock_and_scan(self):
        """Calls `scan_all_subnets()` if the active_discovery lock is acquired.

        This method must run in a thread that may access the database.

        :return: human readable string indicating scan results.
        """
        try:
            with locks.try_active_discovery:
                try:
                    cidrs = self.get_cidrs_and_validate_scan_config()
                except _InvalidScanState as e:
                    return str(e)
                else:
                    if len(cidrs) == 0:
                        return (
                            "Active scanning is not enabled on any subnet. "
                            "Skipping periodic scan."
                        )
                    return self.scan_all_subnets(cidrs)
        except DatabaseLockNotHeld:
            return (
                "Active discovery lock was taken. Another region controller "
                "is already scanning; skipping scan."
            )

    def scanIfNeeded(self):
        """Defers `try_lock_and_scan()` to the database if necessary.

        Also attempts to detect and log clock skew, if detected.

        This method must only be called if discovery is enabled.

        :return: Deferred (or None if it's not time to scan)
        """
        now = self.getCurrentTimestamp()
        if now < self.discovery_last_scan:
            # We could update the timestamp to match. But that could have
            # serious consequences if the system clock is incorrect.
            # So for now, it seems better to just log this.
            log.msg(
                "Active network discovery: Clock skew detected. Last "
                "scan time (%d) is greater than current time (%d). "
                "Skipping scan." % (self.discovery_last_scan, now)
            )
            return None
        elif now >= (self.discovery_last_scan + self.discovery_interval):
            # We hit the next scan interval, so check if we need to scan.
            d = deferToDatabase(self.try_lock_and_scan)
            d.addCallback(self.activeScanComplete)
            return d
        else:
            return None

    def run(self):
        """Called when the TimerService fires indicating it's time to scan.

        Also called by the postgresListener if the configuration changes.

        This function must be careful to trap any errors in any Deferred
        objects it returns, since they will run in the TimerService's
        LoopingCall, and the TimerService will stop running if the call's
        errback is invoked.

        :return: Deferred (or None if no action is necessary)
        """
        # This method needs to be as simple as possible so that it always adds
        # an errback to the Deferred it returns. (Otherwise, the TimerService
        # will silently stop.)
        if self.discovery_enabled is None:
            # The first time the service runs, the last_seen time will not be
            # initialized. So first gather the settings from the database.
            # Subsequent runs do not need to hit the database, since the
            # postgresListener will inform us if the interval or last_scan time
            # changes. (And those values will be double-checked after taking
            # the lock if we decide it's time to scan.)
            d = maybeDeferred(self.refreshDiscoveryConfig)
            d.addErrback(self.refreshFailed)
            return d
        elif self.discovery_enabled:
            d = maybeDeferred(self.scanIfNeeded)
            d.addErrback(self.activeScanFailed)
            return d
        else:
            return None

    def getCurrentTimestamp(self):
        """Returns the absolute current timestamp (in seconds) as an `int`."""
        return int(timezone.now().timestamp())

    def activeScanComplete(self, result):
        """Called when the active scan completes successfully."""
        log.msg("Active network discovery: %s" % result)

    def activeScanFailed(self, failure):
        """Called if the active scan raises an error."""
        log.err(failure, "Active network discovery: periodic scan failed.")

    def refreshFailed(self, failure):
        """Called if refreshing the discovery configuration fails."""
        log.err(
            failure,
            "Active network discovery: error refreshing discovery "
            "configuration.",
        )
