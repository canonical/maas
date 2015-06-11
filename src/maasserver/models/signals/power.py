# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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

from maasserver.enum import POWER_STATE
from maasserver.models import Node
from maasserver.models.signals.base import connect_to_field_change
from maasserver.node_status import QUERY_TRANSITIONS
from maasserver.rpc import getClientFor
from maasserver.utils.orm import (
    post_commit,
    transactional,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.power.poweraction import (
    PowerActionFail,
    UnknownPowerType,
)
from provisioningserver.rpc.cluster import PowerQuery
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    PowerActionAlreadyInProgress,
)
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    FOREVER,
    synchronous,
)
from twisted.internet import reactor
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
)
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger('node_query')

# Amount of time to wait after a node status has been updated to
# perform a power query.
WAIT_TO_QUERY = timedelta(seconds=20)


@transactional
def get_node_cluster_and_power_info(system_id):
    """Get the node, cluster, and power-info for the specified node.

    :return: A ``(node, cluster, power_info)`` tuple, which will be ``(None,
        None, None)`` if the node does not exist.
    """
    # Obtain the node and its nodegroup/cluster.
    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        return None, None, None
    else:
        # Now obtain the node's power information.
        try:
            power_info = node.get_effective_power_info()
        except UnknownPowerType:
            return node, node.nodegroup, None
        else:
            return node, node.nodegroup, power_info


@transactional
def set_node_power_state(system_id, state):
    """Set the power state for the specified node.

    :return: The node, or `None` if the node no longer exists.
    """
    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        return None
    else:
        node.power_state = state
        node.save()
        return node


@asynchronous(timeout=300)
@inlineCallbacks
def update_power_state_of_node(system_id):
    """Query and update the power state of the given node.

    :return: The new power state of the node, a member of the `POWER_STATE`
        enum, or `None` which denotes that the status could not be queried or
        updated for any of a number of reasons; check the log.
    """
    node, cluster, power_info = yield deferToThread(
        get_node_cluster_and_power_info, system_id)

    if node is None:
        # The node may have been deleted before we get to this point. Silently
        # abandon this task; there's no point even logging.
        return

    if not node.installable:
        # This is actually a device, not a node. We don't support power queries
        # for devices.
        return

    if power_info is None:
        # The node does not have a valid power type, so we can't query it.
        # Logging this is just spam; this problem is reported elsewhere, so
        # silently abandon this task.
        return

    if not power_info.can_be_queried:
        # The node explicitly cannot be queried. Again, logging this is just
        # spam, so we silently abandon this task.
        return

    try:
        client = yield getClientFor(cluster.uuid)
    except NoConnectionsAvailable:
        maaslog.warning(
            "%s: Could not check power status (no connection to cluster)",
            node.hostname)
        return

    try:
        response = yield client(
            PowerQuery, system_id=system_id,
            hostname=node.hostname, power_type=power_info.power_type,
            context=power_info.power_parameters)
    except (UnknownPowerType, NotImplementedError):
        # The cluster does not know how to query power for this node.
        power_state = POWER_STATE.UNKNOWN
    except PowerActionAlreadyInProgress:
        # Abandon this task; let the periodic power checker check next.
        power_state = None
    except PowerActionFail as error:
        # Something went wrong.
        power_state = POWER_STATE.ERROR
        maaslog.warning(
            "%s: Failure when checking power state: %s",
            node.hostname, error)
    except Exception as error:
        # Oh noes! Big error!
        power_state = POWER_STATE.ERROR
        maaslog.error(
            "%s: Error when checking power state: %s",
            node.hostname, error)
    else:
        power_state = response["state"]

    if power_state is None:
        # This denotes that no update should be made. Abandon this task.
        return

    node = yield deferToThread(
        set_node_power_state, system_id, power_state)

    if node is None:
        # The node has been deleted since we began querying its power state.
        # Silently abandon this task.
        return

    # The node's still around and has been updated.
    if power_state == POWER_STATE.ERROR:
        maaslog.info("%s: Unable to determine power state.", node.hostname)
    else:
        maaslog.info("%s: Power is %s.", node.hostname, power_state)

    returnValue(power_state)


@asynchronous(timeout=FOREVER)  # This will return very quickly.
def update_power_state_of_node_soon(system_id, clock=reactor):
    """Update the power state of the given node soon, but not immediately.

    This schedules a check of the node's power state after a delay of
    `WAIT_TO_QUERY`.

    :return: A `DelayedCall` instance, describing the pending update. Don't
        use this outside of the reactor thread though!
    """
    return clock.callLater(
        WAIT_TO_QUERY.total_seconds(),
        update_power_state_of_node, system_id)


@synchronous
def signal_update_power_state_of_node(instance, old_values, **kwargs):
    """Updates the power state of a node, when its status changes."""
    node = instance
    [old_status] = old_values

    # Only check the power state if it's an interesting transition.
    if old_status in QUERY_TRANSITIONS:
        if node.status in QUERY_TRANSITIONS[old_status]:
            post_commit().addCallback(
                callOut, update_power_state_of_node_soon, node.system_id)


# The `enable` and `disable` functions should be used by tests only. They are
# not generally useful, and can cause failures if used mid-transaction.
enable, disable = connect_to_field_change(
    signal_update_power_state_of_node, Node, ['status'], delete=False)
