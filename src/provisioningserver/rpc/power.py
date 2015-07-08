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
    "get_power_state",
    "query_all_nodes",
]

from datetime import timedelta
from functools import partial
import sys

from provisioningserver.drivers.power import PowerDriverRegistry
from provisioningserver.events import (
    EVENT_TYPES,
    send_event_node,
)
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.power.poweraction import (
    PowerAction,
    PowerActionFail,
)
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import (
    NoSuchNode,
    PowerActionAlreadyInProgress,
)
from provisioningserver.rpc.region import (
    MarkNodeFailed,
    UpdateNodePowerState,
)
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
    DeferredList,
    DeferredSemaphore,
    inlineCallbacks,
    returnValue,
    succeed,
)
from twisted.internet.task import deferLater
from twisted.internet.threads import deferToThread
from twisted.python import log

# List of power_types that support querying the power state.
# change_power_state() will only retry changing the power
# state for these power types.
# This is meant to be temporary until all the power types support
# querying the power state of a node.
QUERY_POWER_TYPES = [
    'amt',
    'dli',
    'hmc',
    'ipmi',
    'mscm',
    'msftocs',
    'sm15k',
    'ucsm',
    'virsh',
    'vmware',
]


# Timeout for change_power_state(). We set it to 5 minutes by default,
# but it would be lovely if this was configurable. This is only a backstop
# meant to cope with broken BMCs.
CHANGE_POWER_STATE_TIMEOUT = timedelta(minutes=5).total_seconds()


maaslog = get_maas_logger("power")


# We could use a Registry here, but it seems kind of like overkill.
power_action_registry = {}


def is_power_driver_available(power_type):
    return PowerDriverRegistry.get_item(power_type) is not None


@asynchronous
@inlineCallbacks
def power_change_failure(system_id, hostname, power_change, message):
    """Deal with a node failing to be powered up or down."""
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
def perform_power_change(system_id, hostname, power_type, power_change,
                         context):
    """Issue the given `power_change` command.

    If any exception is raised during the execution of the command,
    mark the node as broken and re-raise the exception.
    """
    action = PowerAction(power_type)
    try:
        return action.execute(power_change=power_change, **context)
    except PowerActionFail as error:
        message = "Node could not be powered %s: %s" % (
            power_change, error)
        power_change_failure(
            system_id, hostname, power_change, message).wait(15)
        raise


def perform_power_driver_change(system_id, hostname, power_type, power_change,
                                context):
    """Execute power driver `power_change` method.

    If any exception is raised during the execution of the method,
    mark the node as broken and re-raise the exception.
    """
    try:
        power_driver = PowerDriverRegistry.get_item(power_type)
        if power_change == 'on':
            power_driver.on(**context)
        elif power_change == 'off':
            power_driver.off(**context)
        else:
            raise PowerActionFail(
                "Invalid power change %s" % power_change)
    except PowerActionFail as error:
        message = "Node could not be powered %s: %s" % (
            power_change, error)
        power_change_failure(
            system_id, hostname, power_change, message).wait(15)
        raise


@asynchronous
@inlineCallbacks
def power_change_success(system_id, hostname, power_change):
    assert power_change in ['on', 'off'], (
        "Unknown power change: %s" % power_change)
    yield power_state_update(system_id, power_change)
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


default_waiting_policy = (1, 2, 2, 4, 6, 8, 12)


@asynchronous
@deferred  # Always return a Deferred.
def maybe_change_power_state(system_id, hostname, power_type,
                             power_change, context, clock=reactor):
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
    if system_id in power_action_registry:
        current_power_change, d = power_action_registry[system_id]
    else:
        current_power_change, d = None, None

    if current_power_change is None:
        # Arrange for the power change to happen later; do not make the caller
        # wait, because it might take a long time. We set a timeout of two
        # minutes so that if the power action doesn't return in a timely
        # fashion (or fails silently or some such) it doesn't block other
        # actions on the node.
        d = deferLater(
            clock, 0, deferWithTimeout, CHANGE_POWER_STATE_TIMEOUT,
            change_power_state, system_id, hostname, power_type, power_change,
            context, clock)

        power_action_registry[system_id] = power_change, d

        # Whether we succeed or fail, we need to remove the action from the
        # registry of actions, otherwise subsequent actions will fail.
        d.addBoth(callOut, power_action_registry.pop, system_id, None)

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
def change_power_state(system_id, hostname, power_type, power_change, context,
                       clock=reactor):
    """Change the power state of a node.

    Monitor the result of the power change action by querying the
    power state of the node and mark the node as failed if it doesn't
    work.
    """
    yield power_change_starting(system_id, hostname, power_change)
    # Use increasing waiting times to work around race conditions
    # that could arise when power-cycling the node.
    for waiting_time in default_waiting_policy:
        # Perform power change.
        try:
            # Check if power_type has PowerDriver support.
            if is_power_driver_available(power_type):
                perform_power_driver_change(
                    system_id, hostname, power_type, power_change, context)
            else:
                yield deferToThread(
                    perform_power_change, system_id, hostname, power_type,
                    power_change, context)
        except PowerActionFail:
            raise
        # If the power_type doesn't support querying the power state:
        # exit now.
        if power_type not in QUERY_POWER_TYPES:
            return
        # Wait to let the node some time to change its power state.
        yield pause(waiting_time, clock)
        # Check current power state.
        if is_power_driver_available(power_type):
            new_power_state = yield perform_power_driver_query(
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
        if is_power_driver_available(power_type):
            return

    # Failure: the power state of the node hasn't changed: mark it as
    # broken.
    message = "Timeout after %s tries" % len(default_waiting_policy)
    yield power_change_failure(system_id, hostname, power_change, message)


@asynchronous
def power_state_update(system_id, state):
    """Update a node's power state"""
    client = getRegionClient()
    return client(
        UpdateNodePowerState,
        system_id=system_id,
        power_state=state)


@asynchronous
@inlineCallbacks
def power_query_failure(system_id, hostname, message):
    """Deal with a node failing to be queried."""
    maaslog.error(message)
    yield power_state_update(system_id, 'error')
    yield send_event_node(
        EVENT_TYPES.NODE_POWER_QUERY_FAILED,
        system_id, hostname, message)


@synchronous
def perform_power_query(system_id, hostname, power_type, context):
    """Issue the given `power_query` command.

    No exception handling is performed here, this allows
    `get_power_state` to perform multiple queries and only
    log the final error.
    """
    action = PowerAction(power_type)
    # `power_change` is a misnomer here.
    return action.execute(power_change='query', **context)


@inlineCallbacks
def perform_power_driver_query(system_id, hostname, power_type, context):
    """Issue the given `power_query` command for power driver."""
    # Get power driver for given power type
    power_driver = PowerDriverRegistry[power_type]
    power_state = yield power_driver.query(**context)
    returnValue(power_state)


@asynchronous
@inlineCallbacks
def get_power_state(system_id, hostname, power_type, context, clock=reactor):
    """Return the power state of the given node.

    A side-effect of calling this method is that the power state recorded in
    the database is updated.

    :return: The string "on" or "off".
    :raises PowerActionFail: When `power_type` is not queryable, or when
        there's a failure when querying the node's power state.
    """
    if power_type not in QUERY_POWER_TYPES:
        # query_all_nodes() won't call this with an un-queryable power
        # type, however this is left here to prevent PEBKAC.
        raise PowerActionFail("Unknown power_type '%s'" % power_type)

    def check_power_state(state):
        if state not in ("on", "off", "unknown"):
            # This is considered an error.
            raise PowerActionFail(state)

    # Capture errors as we go along.
    exc_info = None, None, None

    if is_power_driver_available(power_type):
        # New-style power drivers handle retries for themselves, so we only
        # ever call them once.
        try:
            power_state = yield perform_power_driver_query(
                system_id, hostname, power_type, context)
            check_power_state(power_state)
        except:
            # Hold the error; it will be reported later.
            exc_info = sys.exc_info()
        else:
            yield power_state_update(system_id, power_state)
            returnValue(power_state)
    else:
        # Old-style power drivers need to be retried. Use increasing waiting
        # times to work around race conditions that could arise when power
        # querying the node.
        for waiting_time in default_waiting_policy:
            # Perform power query.
            try:
                power_state = yield deferToThread(
                    perform_power_query, system_id, hostname,
                    power_type, context)
                check_power_state(power_state)
            except:
                # Hold the error; it may be reported later.
                exc_info = sys.exc_info()
                # Wait before trying again.
                yield pause(waiting_time, clock)
            else:
                yield power_state_update(system_id, power_state)
                returnValue(power_state)

    # Reaching here means that things have gone wrong.
    assert exc_info != (None, None, None)
    exc_type, exc_value, exc_trace = exc_info
    message = "Power state could not be queried: %s" % (exc_value,)
    yield power_query_failure(system_id, hostname, message)
    raise exc_type, exc_value, exc_trace


def maaslog_report_success(node, power_state):
    """Log change in power state for node."""
    if node['power_state'] != power_state:
        maaslog.info(
            "%s: Power state has changed from %s to %s.", node['hostname'],
            node['power_state'], power_state)
    return power_state


def maaslog_report_failure(node, failure):
    """Log failure to query node."""
    if failure.check(PowerActionFail):
        maaslog.error(
            "%s: Could not query power state: %s.",
            node['hostname'], failure.getErrorMessage())
    elif failure.check(NoSuchNode):
        maaslog.debug(
            "%s: Could not update power state: "
            "no such node.", node['hostname'])
    else:
        maaslog.error(
            "%s: Failed to refresh power state: %s",
            node['hostname'], failure.getErrorMessage())
        # Also write out a full traceback to the server log.
        log.err(failure, "Failed to refresh power state.")


def query_node(node, clock):
    """Calls `get_power_state` on the given node.

    Logs to maaslog as errors and power states change.
    """
    if node['system_id'] in power_action_registry:
        maaslog.debug(
            "%s: Skipping query power status, "
            "power action already in progress.",
            node['hostname'])
        return succeed(None)
    else:
        d = get_power_state(
            node['system_id'], node['hostname'],
            node['power_type'], node['context'],
            clock=clock)
        d.addCallbacks(
            partial(maaslog_report_success, node),
            partial(maaslog_report_failure, node))
        return d


def query_all_nodes(nodes, max_concurrency=5, clock=reactor):
    """Queries the given nodes for their power state.

    Nodes' states are reported back to the region.

    :return: A deferred, which fires once all nodes have been queried,
        successfully or not.
    """
    semaphore = DeferredSemaphore(tokens=max_concurrency)
    queries = (
        semaphore.run(query_node, node, clock)
        for node in nodes if node['power_type'] in QUERY_POWER_TYPES)
    return DeferredList(queries, consumeErrors=True)
