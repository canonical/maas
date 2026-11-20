# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Query power status on node state changes."""

from datetime import timedelta

from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred

from maasserver.enum import NODE_STATUS
from maasserver.exceptions import PowerProblem
from maasserver.models.node import Node
from maasserver.node_status import QUERY_TRANSITIONS
from maasserver.utils.orm import post_commit, transactional
from maasserver.utils.signals import SignalsManager
from maasserver.utils.threads import deferToDatabase
from provisioningserver.enum import POWER_STATE
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

# The single post-deployment query above can land while the BMC is still
# reporting a transitional state, caching a wrong power state indefinitely.
# IBM Z HMC/DPM partitions report "paused" both for a guest-initiated
# shutdown and, transiently, during a normal boot, so a node that is
# running fine ends up shown as "off" until someone clicks "Check power".
# Recheck until the state settles, bounded by roughly MAAS's own
# deployment-task timeout: past that, deployment has very likely already
# failed for unrelated reasons.
DEPLOYED_RECHECK_INTERVAL = timedelta(minutes=5)
DEPLOYED_RECHECK_MAX_ATTEMPTS = 12

# The same HMCs also occasionally return an outright incorrect reading for a
# node verified to be running throughout, so a single "on" isn't conclusive.
# Requiring consecutive agreeing readings keeps the recheck loop alive long
# enough to correct a later bad one. It does not change which value
# Node.power_query() persists per call -- that is shared by every caller.
REQUIRED_CONSECUTIVE_ON_READINGS = 2


@asynchronous(timeout=45)
def update_power_state_of_node(
    system_id,
    recheck_attempts_left=DEPLOYED_RECHECK_MAX_ATTEMPTS,
    consecutive_on_seen=0,
    clock=reactor,
):
    """Query and update the power state of the given node.

    On a boot-order-capable power type, a node that has just finished
    deploying is re-queried every `DEPLOYED_RECHECK_INTERVAL`, up to
    `recheck_attempts_left` times, until "on" has been seen on
    `REQUIRED_CONSECUTIVE_ON_READINGS` consecutive queries.

    :return: The new power state of the node, a member of the `POWER_STATE`
        enum, or `None` which denotes that the status could not be queried or
        updated for any of a number of reasons; check the log.
    """

    def eb_error(failure):
        failure.trap(Node.DoesNotExist, UnknownPowerType, PowerProblem)

    def cb_query(node):
        d = maybeDeferred(node.power_query)
        d.addCallback(lambda power_state: (node, power_state))
        return d

    def cb_maybe_recheck(node_and_state):
        node, power_state = node_and_state
        confirmed_on_count = (
            consecutive_on_seen + 1 if power_state == POWER_STATE.ON else 0
        )

        # Cheap checks first: if any of these already rule out rescheduling,
        # skip the extra database round-trip for the power info below.
        if not (
            recheck_attempts_left > 0
            and node.status == NODE_STATUS.DEPLOYED
            and confirmed_on_count < REQUIRED_CONSECUTIVE_ON_READINGS
        ):
            return power_state

        def cb_maybe_schedule(power_info):
            # Restrict rechecking to boot-order-capable power types, the
            # same flag DeployWorkflow._switch_to_local_boot() gates on.
            # hmcz is currently the only driver setting it, so only IBM Z
            # DPM partitions are affected; this keys off the machine's
            # power type, not the controller's architecture. Any future
            # driver managing its own boot order the same way would
            # plausibly need this too. For every other power type this is
            # a no-op.
            if not power_info.can_set_boot_order:
                return power_state

            if power_state == POWER_STATE.ON:
                log.msg(
                    f"{system_id}: deployed node queried as 'on' "
                    f"({confirmed_on_count}/"
                    f"{REQUIRED_CONSECUTIVE_ON_READINGS} consecutive "
                    "readings); confirming again in "
                    f"{DEPLOYED_RECHECK_INTERVAL.total_seconds():.0f}s."
                )
            else:
                log.msg(
                    f"{system_id}: deployed node queried as "
                    f"'{power_state}', not 'on'; rechecking in "
                    f"{DEPLOYED_RECHECK_INTERVAL.total_seconds():.0f}s "
                    f"({recheck_attempts_left - 1} further attempt(s) "
                    "after that)."
                )
            clock.callLater(
                DEPLOYED_RECHECK_INTERVAL.total_seconds(),
                update_power_state_of_node,
                system_id,
                recheck_attempts_left - 1,
                confirmed_on_count,
                clock,
            )
            return power_state

        d = deferToDatabase(transactional(node.get_effective_power_info))
        d.addCallback(cb_maybe_schedule)
        return d

    d = deferToDatabase(transactional(Node.objects.get), system_id=system_id)
    d.addCallback(cb_query)
    d.addCallback(cb_maybe_recheck)
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
