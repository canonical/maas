# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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
    "maybe_change_power_state",
]

from datetime import timedelta

from provisioningserver import power
from provisioningserver.drivers.power import (
    get_error_message,
    PowerDriverRegistry,
)
from provisioningserver.events import (
    EVENT_TYPES,
    send_event_node,
)
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.power import (
    poweraction,
    query,
)
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import PowerActionAlreadyInProgress
from provisioningserver.rpc.region import MarkNodeFailed
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    deferred,
    deferWithTimeout,
    pause,
    synchronous,
)
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    inlineCallbacks,
)
from twisted.internet.task import deferLater
from twisted.internet.threads import deferToThread
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
    assert power_change in ['on', 'off'], (
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
    yield send_event_node(event_type, system_id, hostname, message)


@synchronous
def perform_power_change(
        system_id, hostname, power_type, power_change, context):
    """Issue the given `power_change` command.

    On failure the node will be marked as broken and the error will be
    re-raised to the caller.

    :deprecated: This relates to template-based power control.
    """
    action = poweraction.PowerAction(power_type)
    try:
        return action.execute(power_change=power_change, **context)
    except poweraction.PowerActionFail as error:
        message = "Node could not be powered %s: %s" % (power_change, error)
        power_change_failure(system_id, hostname, power_change, message)
        raise


@asynchronous
def perform_power_driver_change(
        system_id, hostname, power_type, power_change, context):
    """Execute power driver `power_change` method.

    On failure the node will be marked as broken and the error will be
    re-raised to the caller.
    """
    power_driver = PowerDriverRegistry.get_item(power_type)

    if power_change == 'on':
        d = power_driver.on(**context)
    elif power_change == 'off':
        d = power_driver.off(**context)

    def power_change_failed(failure):
        message = "Node could not be powered %s: %s" % (
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
    :param power_change: "on" or "off".
    """
    assert power_change in ['on', 'off'], (
        "Unknown power change: %s" % power_change)
    maaslog.info(
        "Changing power state (%s) of node: %s (%s)",
        power_change, hostname, system_id)
    # Emit starting event.
    if power_change == 'on':
        event_type = EVENT_TYPES.NODE_POWER_ON_STARTING
    elif power_change == 'off':
        event_type = EVENT_TYPES.NODE_POWER_OFF_STARTING
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
    assert power_change in ('on', 'off'), (
        "Unknown power change: %s" % power_change)

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
                "%s: Power could not be turned %s; timed out."
                % (hostname, power_change))
            return power_change_failure(
                system_id, hostname, power_change, "Timed out")
        d.addErrback(eb_cancelled)

        # Catch-all log.
        d.addErrback(
            log.err, "%s: Power could not be turned %s." % (
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
    # Use increasing waiting times to work around race conditions
    # that could arise when power-cycling the node.
    for waiting_time in power.default_waiting_policy:
        if power.is_driver_available(power_type):
            # There's a Python-based driver for this power type.
            yield perform_power_driver_change(
                system_id, hostname, power_type, power_change, context)
        else:
            # This power type is still template-based.
            yield deferToThread(
                perform_power_change, system_id, hostname, power_type,
                power_change, context)
        # Return now if we can't query the power state.
        if power_type not in power.QUERY_POWER_TYPES:
            return
        # Wait to let the node some time to change its power state.
        yield pause(waiting_time, clock)
        # Check current power state.
        if power.is_driver_available(power_type):
            new_power_state = yield query.perform_power_driver_query(
                system_id, hostname, power_type, context)
        else:
            new_power_state = yield deferToThread(
                perform_power_change, system_id, hostname, power_type,
                'query', context)
        if new_power_state == "unknown" or new_power_state == power_change:
            yield power_change_success(system_id, hostname, power_change)
            return
        # Retry logic is handled by power driver
        # Once all power types have had templates converted to power drivers
        # this method will need to be re-factored.
        if power.is_driver_available(power_type):
            return

    # Failure: the power state of the node hasn't changed: mark it as
    # broken.
    message = "Timeout after %s tries" % len(power.default_waiting_policy)
    yield power_change_failure(system_id, hostname, power_change, message)
