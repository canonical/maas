# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers for timers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "cancel_timer",
    "start_timers",
]

from datetime import datetime

from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import TimerExpired
from twisted.internet import reactor
from twisted.protocols import amp


maaslog = get_maas_logger("timers")


# Currently running timers; contains dict with keys of ID mapping to a
# (delayed_call, context) pair.
running_timers = dict()


def start_timers(timers, clock=reactor):
    """RPC responder to start timers as specified.

    :param timers: a `StartTimers` message.

    Will create one delayed callback for each of the timers and if it
    reaches its deadline, call `TimerExpired` in the region passing back the
    timer ID.
    """
    for timer in timers:
        delay = timer["deadline"] - datetime.now(amp.utc)
        timer_id = timer["id"]
        call = clock.callLater(delay.total_seconds(), timer_expired, timer_id)
        running_timers[timer_id] = (call, timer["context"])


def timer_expired(timer_id):
    """Called when a timer hits its deadline.

    Call TimerExpired with the context for the timer.
    """
    _, context = running_timers.pop(timer_id)
    try:
        client = getRegionClient()
    except NoConnectionsAvailable:
        maaslog.error(
            "Lost connection to the region, unable to fire timer with ID: %s",
            timer_id)
        return None

    return client(TimerExpired, id=timer_id, context=context)


def cancel_timer(timer_id):
    """Called from the region to cancel a running timer."""
    try:
        dc, _ = running_timers.pop(timer_id)
    except KeyError:
        return
    dc.cancel()
