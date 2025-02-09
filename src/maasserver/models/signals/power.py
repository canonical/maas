# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Query power status on node state changes."""

from datetime import timedelta

from twisted.internet import reactor

from maasserver.exceptions import PowerProblem
from maasserver.models.node import Node
from maasserver.node_status import QUERY_TRANSITIONS
from maasserver.utils.orm import post_commit, transactional
from maasserver.utils.signals import SignalsManager
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.rpc.exceptions import UnknownPowerType
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    FOREVER,
    synchronous,
)

log = LegacyLogger()


signals = SignalsManager()

# Amount of time to wait after a node status has been updated to
# perform a power query.
WAIT_TO_QUERY = timedelta(seconds=20)


@asynchronous(timeout=45)
def update_power_state_of_node(system_id):
    """Query and update the power state of the given node.

    :return: The new power state of the node, a member of the `POWER_STATE`
        enum, or `None` which denotes that the status could not be queried or
        updated for any of a number of reasons; check the log.
    """

    def eb_error(failure):
        failure.trap(Node.DoesNotExist, UnknownPowerType, PowerProblem)

    d = deferToDatabase(transactional(Node.objects.get), system_id=system_id)
    d.addCallback(lambda node: node.power_query())
    d.addErrback(eb_error)
    d.addErrback(
        log.err,
        "Failed to update power state of machine after state transition.",
    )
    return d


@asynchronous(timeout=FOREVER)  # This will return very quickly.
def update_power_state_of_node_soon(system_id, clock=reactor):
    """Update the power state of the given node soon, but not immediately.

    This schedules a check of the node's power state after a delay of
    `WAIT_TO_QUERY`.

    :return: A `DelayedCall` instance, describing the pending update. Don't
        use this outside of the reactor thread though!
    """
    return clock.callLater(
        WAIT_TO_QUERY.total_seconds(), update_power_state_of_node, system_id
    )


@synchronous
def signal_update_power_state_of_node(instance, old_values, **kwargs):
    """Updates the power state of a node, when its status changes."""
    node = instance
    [old_status] = old_values

    # Only check the power state if it's an interesting transition.
    if old_status in QUERY_TRANSITIONS:
        if node.status in QUERY_TRANSITIONS[old_status]:
            post_commit().addCallback(
                callOut, update_power_state_of_node_soon, node.system_id
            )


signals.watch_fields(signal_update_power_state_of_node, Node, ["status"])


# Enable all signals by default.
signals.enable()
