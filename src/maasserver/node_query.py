# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Query power status on node state changes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from datetime import timedelta

from crochet import TimeoutError
from maasserver.enum import POWER_STATE
from maasserver.models import Node
from maasserver.node_status import QUERY_TRANSITIONS
from maasserver.rpc import getClientFor
from maasserver.signals import connect_to_field_change
from maasserver.utils.async import transactional
from provisioningserver.logger import get_maas_logger
from provisioningserver.power.poweraction import (
    PowerActionFail,
    UnknownPowerType,
    )
from provisioningserver.rpc.cluster import PowerQuery
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils.twisted import synchronous
from twisted.internet import reactor
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger('node_query')

# Amount of time to wait after a node status has been updated to
# perform a power query.
WAIT_TO_QUERY = timedelta(seconds=20)


@synchronous
@transactional
def update_power_state_of_node(system_id):
    """Update the power state of the given node."""
    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        # Just in case the Node has been deleted,
        # before we get to this point.
        return

    try:
        client = getClientFor(node.nodegroup.uuid)
    except NoConnectionsAvailable:
        maaslog.error(
            "Unable to get RPC connection for cluster '%s' (%s)",
            node.nodegroup.cluster_name, node.nodegroup.uuid)
        return

    try:
        power_info = node.get_effective_power_info()
    except UnknownPowerType:
        return
    if not power_info.can_be_started:
        # Power state is not queryable
        return

    call = client(
        PowerQuery, system_id=system_id, hostname=node.hostname,
        power_type=power_info.power_type,
        context=power_info.power_parameters)
    try:
        state = call.wait(30).get("state", POWER_STATE.ERROR)
    except (TimeoutError, NotImplementedError, PowerActionFail):
        state = POWER_STATE.ERROR
    node.power_state = state
    node.save()


def wait_to_update_power_state_of_node(system_id, clock=reactor):
    """Wait "WAIT_TO_QUERY" amount of time then update the power state of
    the given node."""
    clock.callLater(
        WAIT_TO_QUERY.total_seconds(), deferToThread,
        update_power_state_of_node, system_id)


@synchronous
def signal_update_power_state_of_node(instance, old_values, **kwargs):
    """Updates the power state of a node, when its status changes."""
    node = instance
    [old_status] = old_values

    # Check if this transition should even check for a new power state.
    if old_status not in QUERY_TRANSITIONS:
        return
    if node.status not in QUERY_TRANSITIONS[old_status]:
        return

    # Update the power state of the node, after the waiting period.
    wait_to_update_power_state_of_node(node.system_id)


connect_to_field_change(
    signal_update_power_state_of_node,
    Node, ['status'], delete=False)
