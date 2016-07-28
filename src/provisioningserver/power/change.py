# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to power control."""

__all__ = [
    "maybe_change_power_state",
]

from datetime import timedelta

from provisioningserver import power
from provisioningserver.drivers.power import (
    get_error_message,
    power_drivers_by_name,
    PowerDriverRegistry,
)
from provisioningserver.events import (
    EVENT_TYPES,
    send_event_node,
)
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.power import query
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import (
    PowerActionAlreadyInProgress,
    PowerActionFail,
)
from provisioningserver.rpc.region import MarkNodeFailed
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    deferred,
    deferWithTimeout,
)
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    inlineCallbacks,
    returnValue,
)
from twisted.internet.task import deferLater
from twisted.python import log


maaslog = get_maas_logger("power")


# Timeout for change_power_state(). We set it to 5 minutes by default,
# but it would be lovely if this was configurable. This is only a backstop
# meant to cope with broken BMCs.
CHANGE_POWER_STATE_TIMEOUT = timedelta(minutes=5).total_seconds()


@asynchronous(timeout=15)
@inlineCallbacks
def power_change_failure(system_id, hostname, power_change, message):
    """Report a node that for which power control has failed."""
    assert power_change in ['on', 'off', 'cycle'], (
        "Unknown power change: %s" % power_change)
    maaslog.error(
        "Error changing power state (%s) of node: %s (%s)",
        power_change, hostname, system_id)
    client = getRegionClient()
    yield client(
        MarkNodeFailed,
        system_id=system_id,
        error_description=message,
    )
    if power_change == 'on':
        event_type = EVENT_TYPES.NODE_POWER_ON_FAILED
    elif power_change == 'off':
        event_type = EVENT_TYPES.NODE_POWER_OFF_FAILED
    elif power_change == 'cycle':
        event_type = EVENT_TYPES.NODE_POWER_CYCLE_FAILED
    yield send_event_node(event_type, system_id, hostname, message)


@asynchronous
def perform_power_driver_change(
        system_id, hostname, power_type, power_change, context):
    """Execute power driver `power_change` method.

    On failure the node will be marked as broken and the error will be
    re-raised to the caller.
    """
    power_driver = PowerDriverRegistry.get_item(power_type)

    if power_change == 'on':
        d = power_driver.on(system_id, context)
    elif power_change == 'off':
        d = power_driver.off(system_id, context)
    elif power_change == 'cycle':
        d = power_driver.cycle(system_id, context)

    def power_change_failed(failure):
        message = "Power %s for the node failed: %s" % (
            power_change, get_error_message(failure.value))
        df = power_change_failure(system_id, hostname, power_change, message)
        df.addCallback(lambda _: failure)  # Propagate the original error.
        return df

    return d.addErrback(power_change_failed)


@asynchronous
@inlineCallbacks
def power_change_success(system_id, hostname, power_change):
    """Report about a successful node power state change.

    This updates the region's record of the node's power state, logs to the
    MAAS log, and appends to the node's event log.

    :param system_id: The system ID for the node.
    :param hostname: The node's hostname, used in messages.
    :param power_change: "on" or "off".
    """
    assert power_change in ['on', 'off'], (
        "Unknown power change: %s" % power_change)
    yield power.power_state_update(system_id, power_change)
    maaslog.info(
        "Changed power state (%s) of node: %s (%s)",
        power_change, hostname, system_id)
    # Emit success event.
    if power_change == 'on':
        event_type = EVENT_TYPES.NODE_POWERED_ON
    elif power_change == 'off':
        event_type = EVENT_TYPES.NODE_POWERED_OFF
    yield send_event_node(event_type, system_id, hostname)


@asynchronous
@inlineCallbacks
def power_change_starting(system_id, hostname, power_change):
    """Report about a node power state change starting.

    This logs to the MAAS log, and appends to the node's event log.

    :param system_id: The system ID for the node.
    :param hostname: The node's hostname, used in messages.
    :param power_change: "on", "off", or "cycle".
    """
    assert power_change in ['on', 'off', 'cycle'], (
        "Unknown power change: %s" % power_change)
    maaslog.info(
        "Changing power state (%s) of node: %s (%s)",
        power_change, hostname, system_id)
    # Emit starting event.
    if power_change == 'on':
        event_type = EVENT_TYPES.NODE_POWER_ON_STARTING
    elif power_change == 'off':
        event_type = EVENT_TYPES.NODE_POWER_OFF_STARTING
    elif power_change == 'cycle':
        event_type = EVENT_TYPES.NODE_POWER_CYCLE_STARTING
    yield send_event_node(event_type, system_id, hostname)


@asynchronous
@deferred  # Always return a Deferred.
def maybe_change_power_state(
        system_id, hostname, power_type, power_change, context,
        clock=reactor):
    """Attempt to change the power state of a node.

    If there is no power action already in progress, register this
    action and then pass change_power_state() to the reactor to call
    later and then return.

    This function exists to guarantee that PowerActionAlreadyInProgress
    errors will be raised promptly, before any work is done to power the
    node on.

    :raises: PowerActionAlreadyInProgress if there's already a power
        action in progress for this node.
    """
    assert power_change in ('on', 'off', 'cycle'), (
        "Unknown power change: %s" % power_change)

    power_driver = power_drivers_by_name.get(power_type)
    if power_driver is None:
        raise PowerActionFail(
            "Unknown power_type '%s'" % power_type)
    missing_packages = power_driver.detect_missing_packages()
    if len(missing_packages):
        raise PowerActionFail(
            "'%s' package(s) are not installed" % " ".join(
                missing_packages))

    # There should be one and only one power change for each system ID.
    if system_id in power.power_action_registry:
        current_power_change, d = power.power_action_registry[system_id]
    else:
        current_power_change, d = None, None

    if current_power_change is None:
        # Arrange for the power change to happen later; do not make the caller
        # wait, because it might take a long time. We set a timeout so that if
        # the power action doesn't return in a timely fashion (or fails
        # silently or some such) it doesn't block other actions on the node.
        d = deferLater(
            clock, 0, deferWithTimeout, CHANGE_POWER_STATE_TIMEOUT,
            change_power_state, system_id, hostname, power_type, power_change,
            context, clock)

        power.power_action_registry[system_id] = power_change, d

        # Whether we succeed or fail, we need to remove the action from the
        # registry of actions, otherwise subsequent actions will fail.
        d.addBoth(callOut, power.power_action_registry.pop, system_id, None)

        # Log cancellations distinctly from other errors.
        def eb_cancelled(failure):
            failure.trap(CancelledError)
            log.msg(
                "%s: Power could not be set to %s; timed out."
                % (hostname, power_change))
            return power_change_failure(
                system_id, hostname, power_change, "Timed out")
        d.addErrback(eb_cancelled)

        # Catch-all log.
        d.addErrback(
            log.err, "%s: Power %s failed." % (
                hostname, power_change))

    elif current_power_change == power_change:
        # What we want is already happening; let it continue.
        pass

    else:
        # Right now we reject conflicting power changes. However, we have the
        # Deferred (in `d`) along which the current power change is occurring,
        # so the option to cancel is available if we want it.
        raise PowerActionAlreadyInProgress(
            "Unable to change power state to '%s' for node %s: another "
            "action is already in progress for that node." %
            (power_change, hostname))


@asynchronous
@inlineCallbacks
def change_power_state(
        system_id, hostname, power_type, power_change, context,
        clock=reactor):
    """Change the power state of a node.

    This monitors the result of the power change by querying the power state
    of the node, thus attempting to ensure that the requested change has taken
    place.

    Success is reported using `power_change_success`. Power-related failures
    are reported using `power_change_failure`. Other failures must be reported
    by the caller.
    """
    yield power_change_starting(system_id, hostname, power_change)
    yield perform_power_driver_change(
        system_id, hostname, power_type, power_change, context)
    if power_type not in power.QUERY_POWER_TYPES:
        returnValue(None)
    new_power_state = yield query.perform_power_driver_query(
        system_id, hostname, power_type, context)
    if new_power_state == "unknown" or new_power_state == power_change:
        yield power_change_success(system_id, hostname, power_change)
    elif new_power_state == 'on' and power_change == 'cycle':
        yield power_change_success(system_id, hostname, new_power_state)
    returnValue(new_power_state)
