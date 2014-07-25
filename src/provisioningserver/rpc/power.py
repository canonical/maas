# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to power control."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "change_power_state",
]


from provisioningserver.power.poweraction import PowerAction
from provisioningserver.rpc import getRegionClient
from provisioningserver.utils import pause
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread

# List of power_types that support querying the power state.
# change_power_state() will only retry changing the power
# state for these power types.
# This is meant to be temporary until all the power types support
# querying the power state of a node.
QUERY_POWER_TYPES = ['amt', 'ipmi']


def perform_power_change(system_id, power_type, power_change, context):
    """Issue the given `power_change` command.

    If any exception is raised during the execution of the command, mark
    the node as broken and re-raise the exception.
    """
    action = PowerAction(power_type)
    try:
        return action.execute(power_change=power_change, **context)
    except Exception as error:
        client = getRegionClient()
        message = "Node could not be powered %s: %s" % (
            power_change, error)
        client.mark_node_broken(system_id, message)
        raise


@inlineCallbacks
def change_power_state(system_id, power_type, power_change, context,
                       clock=reactor):
    """Change the power state of a node.

    Monitor the result of the power change action by querying the
    power state of the node and mark the node as failed if it doesn't
    work.
    """
    assert power_change in ('on', 'off'), (
        "Unknown power change: %s" % power_change)

    # Use increasing waiting times to work around race conditions that could
    # arise when power-cycling the node.
    for waiting_time in (3, 5, 10):
        # Perform power change.
        yield deferToThread(
            perform_power_change, system_id, power_type, power_change,
            context)
        # If the power_type doesn't support querying the power state:
        # exit now.
        if power_type not in QUERY_POWER_TYPES:
            return
        # Wait to let the node some time to change its power state.
        yield pause(waiting_time, clock)
        # Check current power state.
        new_power_state = yield deferToThread(
            perform_power_change, system_id, power_type, 'query', context)
        if new_power_state == power_change:
            return

    # Failure: the power state of the node hasn't changed: mark it as broken.
    client = getRegionClient()
    client.mark_node_broken(
        system_id, "Node could not be powered %s" % power_change)
