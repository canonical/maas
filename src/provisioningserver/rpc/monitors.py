# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers for monitors."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "cancel_monitor",
    "start_monitors",
]

from datetime import datetime

from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import MonitorExpired
from twisted.internet import reactor
from twisted.protocols import amp


maaslog = get_maas_logger("monitors")


# Currently running timers; contains dict with keys of ID mapping to a
# (delayed_call, context) pair.
running_monitors = dict()


def start_monitors(monitors, clock=reactor):
    """RPC responder to start monitors as specified.

    :param monitors: a `StartMonitors` message.

    Right now the monitors only implement a timer.

    Will create one delayed callback for each of the monitors and if it
    reaches its deadline, call `MonitorExpired` in the region passing back the
    monitor ID.
    """
    for monitor in monitors:
        delay = monitor["deadline"] - datetime.now(amp.utc)
        monitor_id = monitor["id"]
        if monitor_id in running_monitors:
            dc, _ = running_monitors.pop(monitor_id)
            dc.cancel()
        call = clock.callLater(
            delay.total_seconds(), monitor_expired, monitor_id)
        running_monitors[monitor_id] = (call, monitor["context"])


def monitor_expired(monitor_id):
    """Called when a monitor hits its deadline.

    Call MonitorExpired with the context for the monitor.
    """
    _, context = running_monitors.pop(monitor_id)
    try:
        client = getRegionClient()
    except NoConnectionsAvailable:
        maaslog.error(
            "Lost connection to the region, unable to fire timer with ID: %s",
            monitor_id)
        return None

    return client(MonitorExpired, id=monitor_id, context=context)


def cancel_monitor(monitor_id):
    """Called from the region to cancel a running timer."""
    try:
        dc, _ = running_monitors.pop(monitor_id)
    except KeyError:
        return
    dc.cancel()
