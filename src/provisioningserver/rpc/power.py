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
    "get_power_state"
]


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
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import (
    ListNodePowerParameters,
    MarkNodeBroken,
    UpdateNodePowerState,
    )
from provisioningserver.utils.twisted import pause
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )
from twisted.internet.threads import deferToThread

# List of power_types that support querying the power state.
# change_power_state() will only retry changing the power
# state for these power types.
# This is meant to be temporary until all the power types support
# querying the power state of a node.
QUERY_POWER_TYPES = ['amt', 'ipmi']


maaslog = get_maas_logger("power")


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
        MarkNodeBroken,
        system_id=system_id,
        error_description=message,
    )
    if power_change == 'on':
        event_type = EVENT_TYPES.NODE_POWER_ON_FAILED
    elif power_change == 'off':
        event_type = EVENT_TYPES.NODE_POWER_OFF_FAILED
    yield send_event_node(event_type, system_id, hostname, message)


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
        power_change_failure(system_id, hostname, power_change, message)
        raise


@inlineCallbacks
def power_change_success(system_id, hostname, power_change):
    assert power_change in ['on', 'off'], (
        "Unknown power change: %s" % power_change)
    power_state_update(system_id, power_change)
    maaslog.info(
        "Changed power state (%s) of node: %s (%s)",
        power_change, hostname, system_id)
    # Emit success event.
    if power_change == 'on':
        event_type = EVENT_TYPES.NODE_POWERED_ON
    elif power_change == 'off':
        event_type = EVENT_TYPES.NODE_POWERED_OFF
    yield send_event_node(event_type, system_id, hostname)


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


default_waiting_policy = (3, 5, 10)


@inlineCallbacks
def change_power_state(system_id, hostname, power_type, power_change, context,
                       clock=reactor):
    """Change the power state of a node.

    Monitor the result of the power change action by querying the
    power state of the node and mark the node as failed if it doesn't
    work.
    """
    assert power_change in ('on', 'off'), (
        "Unknown power change: %s" % power_change)

    yield power_change_starting(system_id, hostname, power_change)
    # Use increasing waiting times to work around race conditions that could
    # arise when power-cycling the node.
    for waiting_time in default_waiting_policy:
        # Perform power change.
        yield deferToThread(
            perform_power_change, system_id, hostname, power_type,
            power_change, context)
        # If the power_type doesn't support querying the power state:
        # exit now.
        if power_type not in QUERY_POWER_TYPES:
            return
        # Wait to let the node some time to change its power state.
        yield pause(waiting_time, clock)
        # Check current power state.
        new_power_state = yield deferToThread(
            perform_power_change, system_id, hostname, power_type,
            'query', context)
        if new_power_state == power_change:
            power_change_success(system_id, hostname, power_change)
            return

    # Failure: the power state of the node hasn't changed: mark it as
    # broken.
    message = "Timeout after %s tries" % len(default_waiting_policy)
    yield power_change_failure(system_id, hostname, power_change, message)


@inlineCallbacks
def power_state_update(system_id, state):
    """Update a node's power state"""
    client = getRegionClient()
    yield client(
        UpdateNodePowerState,
        system_id=system_id,
        power_state=state,
    )


@inlineCallbacks
def power_query_failure(system_id, hostname, message):
    """Deal with a node failing to be queried."""
    maaslog.error(message)
    client = getRegionClient()
    yield client(
        MarkNodeBroken,
        system_id=system_id,
        error_description=message,
    )
    yield send_event_node(
        EVENT_TYPES.NODE_POWER_QUERY_FAILED,
        system_id, hostname, message)


def perform_power_query(system_id, hostname, power_type, context):
    """Issue the given `power_query` command.

    No exception handling is performed here, this allows
    `get_power_state` to perform multiple queries and only
    log the final error.
    """
    action = PowerAction(power_type)
    return action.execute(power_change='query', **context)


@inlineCallbacks
def get_power_state(system_id, hostname, power_type, context, clock=reactor):
    if power_type not in QUERY_POWER_TYPES:
        returnValue('unknown')

    # Use increasing waiting times to work around race conditions that could
    # arise when power querying the node.
    for waiting_time in (3, 5, 10):
        error = None
        # Perform power query.
        try:
            power_state = yield deferToThread(
                perform_power_query, system_id, hostname, power_type, context)
        except PowerActionFail as e:
            # Hold the error so if failure after retries, we can
            # log the reason.
            error = e

            # Wait before trying again.
            yield pause(waiting_time, clock)
            continue
        returnValue(power_state)

    # Send node is broken, since query failed after the multiple retries.
    message = "Node could not be queried %s (%s) %s" % (
        system_id, hostname, error)
    power_query_failure(system_id, hostname, message)
    returnValue('error')


@inlineCallbacks
def query_all_nodes(nodes, clock=reactor):
    """Performs `power_query` on all nodes. If the nodes state has changed,
    then that is sent back to the region."""
    for node in nodes:
        system_id = node['system_id']
        hostname = node['hostname']
        state = yield get_power_state(
            system_id, hostname,
            node['power_type'], node['context'], clock=clock)
        if state != node['state']:
            maaslog.info(
                "Observed power state change for node: %s (%s) changed from "
                "%s -> %s",
                hostname, system_id, node['state'], state)
            power_state_update(system_id, state)


class NodePowerMonitorService(TimerService, object):
    """Twisted service to monitor the status of all nodes
    controlled by this cluster.

    :param client_service: A `ClusterClientService` instance for talking
        to the region controller.
    :param reactor: An `IReactor` instance.
    """

    check_interval = 600  # 5 minutes.

    def __init__(self, client_service, reactor, cluster_uuid):
        # Call self.check() every self.check_interval.
        super(NodePowerMonitorService, self).__init__(
            self.check_interval, self.query_nodes)
        self.clock = reactor
        self.client_service = client_service
        self.uuid = cluster_uuid

    @inlineCallbacks
    def query_nodes(self):
        client = None
        # Retry a few times, since this service usually comes up before
        # the RPC service.
        for _ in range(3):
            try:
                client = self.client_service.getClient()
                break
            except NoConnectionsAvailable:
                yield pause(5)
        if client is None:
            maaslog.error(
                "Can't query nodes's BMC for power state, no RPC connection "
                "to region.")
            return

        # Get the nodes from the Region
        response = yield client(ListNodePowerParameters, uuid=self.uuid)
        nodes = response['nodes']
        yield query_all_nodes(nodes)
