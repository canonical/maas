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

from functools import partial
import sys

from provisioningserver import power
from provisioningserver.drivers.power import PowerDriverRegistry
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


@asynchronous
@inlineCallbacks
def power_query_failure(system_id, hostname, message):
    """Report a node that for which power querying has failed."""
    maaslog.error(message)
    yield power.power_state_update(system_id, 'error')
    yield send_event_node(
        EVENT_TYPES.NODE_POWER_QUERY_FAILED,
        system_id, hostname, message)


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
    return power_driver.query(**context)


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
            yield power.power_state_update(system_id, power_state)
            returnValue(power_state)
    else:
        # Old-style power drivers need to be retried. Use increasing waiting
        # times to work around race conditions that could arise when power
        # querying the node.
        for waiting_time in power.default_waiting_policy:
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
                yield power.power_state_update(system_id, power_state)
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
        for node in nodes if node['power_type'] in power.QUERY_POWER_TYPES)
    return DeferredList(queries, consumeErrors=True)
