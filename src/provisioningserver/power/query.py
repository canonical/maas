# Copyright 2015 Canonical Ltd.  This software is licensed under the
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

from functools import partial
import sys

from provisioningserver import power
from provisioningserver.drivers.power import (
    DEFAULT_WAITING_POLICY,
    power_drivers_by_name,
    PowerDriverRegistry,
)
from provisioningserver.events import (
    EVENT_TYPES,
    send_event_node,
)
from provisioningserver.logger.log import get_maas_logger
from provisioningserver.power import poweraction
from provisioningserver.rpc.exceptions import NoSuchNode
from provisioningserver.utils.twisted import (
    asynchronous,
    pause,
    synchronous,
)
from twisted.internet import reactor
from twisted.internet.defer import (
    DeferredList,
    DeferredSemaphore,
    inlineCallbacks,
    returnValue,
    succeed,
)
from twisted.internet.threads import deferToThread
from twisted.python import log


maaslog = get_maas_logger("power")


@synchronous
def perform_power_query(system_id, hostname, power_type, context):
    """Query the node's power state.

    No exception handling is performed here. This allows `get_power_state` to
    perform multiple queries and only log the final error.

    :param power_type: This must refer to one of the template-based power
        drivers, and *not* to a Python-based one.

    :deprecated: This relates to template-based power control.
    """
    action = poweraction.PowerAction(power_type)
    # `power_change` is a misnomer here.
    return action.execute(power_change='query', **context)


@asynchronous
def perform_power_driver_query(system_id, hostname, power_type, context):
    """Query the node's power state.

    No exception handling is performed here. This allows `get_power_state` to
    perform multiple queries and only log the final error.

    :param power_type: This must refer to one of the Python-based power
        drivers, and *not* to a template-based one.
    """
    # Get power driver for given power type
    power_driver = PowerDriverRegistry[power_type]
    return power_driver.query(system_id, context)


@asynchronous
@inlineCallbacks
def get_power_state(system_id, hostname, power_type, context, clock=reactor):
    """Return the power state of the given node.

    :return: The string "on" or "off".
    :raises PowerActionFail: When `power_type` is not queryable, or when
        there's a failure when querying the node's power state.
    """
    if power_type not in power.QUERY_POWER_TYPES:
        # query_all_nodes() won't call this with an un-queryable power
        # type, however this is left here to prevent PEBKAC.
        raise poweraction.PowerActionFail(
            "Unknown power_type '%s'" % power_type)

    def check_power_state(state):
        if state not in ("on", "off", "unknown"):
            # This is considered an error.
            raise poweraction.PowerActionFail(state)

    # Capture errors as we go along.
    exc_info = None, None, None

    power_driver = power_drivers_by_name.get(power_type)
    if power_driver is None:
        raise poweraction.PowerActionFail(
            "Unknown power_type '%s'" % power_type)
    missing_packages = power_driver.detect_missing_packages()
    if len(missing_packages):
        raise poweraction.PowerActionFail(
            "'%s' package(s) are not installed" % ", ".join(
                missing_packages))

    if power.is_driver_available(power_type):
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
            returnValue(power_state)
    else:
        # Old-style power drivers need to be retried. Use increasing waiting
        # times to work around race conditions that could arise when power
        # querying the node.
        for waiting_time in DEFAULT_WAITING_POLICY:
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
                returnValue(power_state)

    # Reaching here means that things have gone wrong.
    assert exc_info != (None, None, None)
    exc_type, exc_value, exc_trace = exc_info
    raise exc_type, exc_value, exc_trace


@inlineCallbacks
def power_query_success(system_id, hostname, state):
    """Report a node that for which power querying has succeeded."""
    yield power.power_state_update(system_id, state)


@inlineCallbacks
def power_query_failure(system_id, hostname, failure):
    """Report a node that for which power querying has failed."""
    message = "Power state could not be queried: %s"
    message %= failure.getErrorMessage()
    maaslog.error(message)
    yield power.power_state_update(system_id, 'error')
    yield send_event_node(
        EVENT_TYPES.NODE_POWER_QUERY_FAILED,
        system_id, hostname, message)


@asynchronous
def report_power_state(d, system_id, hostname):
    """Report the result of a power query.

    :param d: A `Deferred` that will fire with the node's updated power state,
        or an error condition. The callback/errback values are passed through
        unaltered. See `get_power_state` for details.
    """
    def cb(state):
        d = power_query_success(system_id, hostname, state)
        d.addCallback(lambda _: state)
        return d

    def eb(failure):
        d = power_query_failure(system_id, hostname, failure)
        d.addCallback(lambda _: failure)
        return d

    return d.addCallbacks(cb, eb)


def maaslog_report_success(node, power_state):
    """Log change in power state for node."""
    if node['power_state'] != power_state:
        maaslog.info(
            "%s: Power state has changed from %s to %s.", node['hostname'],
            node['power_state'], power_state)
    return power_state


def maaslog_report_failure(node, failure):
    """Log failure to query node."""
    if failure.check(poweraction.PowerActionFail):
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
    if node['system_id'] in power.power_action_registry:
        maaslog.debug(
            "%s: Skipping query power status, "
            "power action already in progress.",
            node['hostname'])
        return succeed(None)
    else:
        d = get_power_state(
            node['system_id'], node['hostname'], node['power_type'],
            node['context'], clock=clock)
        d = report_power_state(d, node['system_id'], node['hostname'])
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
        for node in nodes if node['power_type'] in power.QUERY_POWER_TYPES)
    return DeferredList(queries, consumeErrors=True)
