# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to nodes."""

__all__ = [
    "mark_node_failed",
    "update_node_power_state",
    "commission_node",
    "create_node",
]

from datetime import timedelta
import json

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import F, Q

from maasserver import exceptions, ntp
from maasserver.api.utils import get_overridden_query_dict
from maasserver.enum import NODE_STATUS
from maasserver.forms import AdminMachineWithMACAddressesForm
from maasserver.models import Node, PhysicalInterface, RackController
from maasserver.models.timestampedmodel import now
from maasserver.utils.orm import transactional
from provisioningserver.drivers.power.registry import PowerDriverRegistry
from provisioningserver.rpc.exceptions import (
    CommissionNodeFailed,
    NodeAlreadyExists,
    NodeStateViolation,
    NoSuchCluster,
    NoSuchNode,
)
from provisioningserver.utils.twisted import synchronous


@synchronous
@transactional
def mark_node_failed(system_id, error_description):
    """Mark a node as failed.

    for :py:class:`~provisioningserver.rpc.region.MarkNodeFailed`.
    """
    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        raise NoSuchNode.from_system_id(system_id)
    try:
        node.mark_failed(comment=error_description)
    except exceptions.NodeStateViolation as e:
        raise NodeStateViolation(e)


def _gen_cluster_nodes_power_parameters(nodes, limit):
    """Generate power parameters for `nodes`.

    These fulfil a subset of the return schema for the RPC call for
    :py:class:`~provisioningserver.rpc.region.ListNodePowerParameters`.

    :return: A generator yielding `dict`s.
    """
    five_minutes_ago = now() - timedelta(minutes=5)
    queryable_power_types = [
        driver.name for _, driver in PowerDriverRegistry if driver.queryable
    ]

    qs = (
        nodes.exclude(status=NODE_STATUS.BROKEN)
        .filter(bmc__power_type__in=queryable_power_types)
        .filter(
            Q(power_state_queried=None)
            | Q(power_state_queried__lte=five_minutes_ago)
        )
        .order_by(F("power_state_queried").asc(nulls_first=True), "system_id")
        .distinct()
    )
    for node in qs[:limit]:
        power_info = node.get_effective_power_info()
        if power_info.power_type is not None:
            yield {
                "system_id": node.system_id,
                "hostname": node.hostname,
                "power_state": node.power_state,
                "power_type": power_info.power_type,
                "context": power_info.power_parameters,
            }


def _gen_up_to_json_limit(things, limit):
    """Yield until the combined JSON dump of those things would exceed `limit`.

    :param things: Any iterable whose elements can dumped as JSON.
    :return: A generator that yields items from `things` unmodified, and in
        order, though maybe not all of them.
    """
    # Deduct the space required for brackets. json.dumps(), by default, does
    # not add padding, so it's just the opening and closing brackets.
    limit -= 2

    for index, thing in enumerate(things):
        # Adjust the limit according the the size of thing.
        if index == 0:
            # A sole element does not need a delimiter.n
            limit -= len(json.dumps(thing))
        else:
            # There is a delimiter between this and the preceeding element.
            # json.dumps(), by default, uses ", ", i.e. 2 characters.
            limit -= len(json.dumps(thing)) + 2

        # Check if we've reached the limit.
        if limit == 0:
            yield thing
            break
        elif limit > 0:
            yield thing
        else:
            break


@synchronous
@transactional
def list_cluster_nodes_power_parameters(system_id, limit=10):
    """Return power parameters that a rack controller should power check,
    in priority order.

    For :py:class:`~provisioningserver.rpc.region.ListNodePowerParameters`.

    :param limit: Limit the number of nodes for which to return power
        parameters. Pass `None` to remove this numerical limit; there is still
        a limit on the quantity of power information that will be returned.
    """
    try:
        rack = RackController.objects.get(system_id=system_id)
    except RackController.DoesNotExist:
        raise NoSuchCluster.from_uuid(system_id)

    # Generate all the the power queries that will fit into the response.
    nodes = rack.get_bmc_accessible_nodes()
    details = _gen_cluster_nodes_power_parameters(nodes, limit)
    details = _gen_up_to_json_limit(details, 60 * (2**10))  # 60kiB
    details = list(details)

    # Update the queried time on all of the nodes at once. So another
    # rack controller does not update them at the same time. This operation
    # is done on all nodes at the same time in one query.
    system_ids = [detail["system_id"] for detail in details]
    Node.objects.filter(system_id__in=system_ids).update(
        power_state_queried=now()
    )

    return details


@synchronous
@transactional
def update_node_power_state(system_id, power_state):
    """Update a node power state.

    for :py:class:`~provisioningserver.rpc.region.UpdateNodePowerState.
    """
    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        raise NoSuchNode.from_system_id(system_id)
    node.update_power_state(power_state)


@synchronous
@transactional
def create_node(
    architecture,
    power_type,
    power_parameters,
    mac_addresses,
    domain=None,
    hostname=None,
):
    """Create a new `Node` and return it.

    :param architecture: The architecture of the new node.
    :param power_type: The power type of the new node.
    :param power_parameters: A JSON-encoded string of power parameters
        for the new node.
    :param mac_addresses: An iterable of MAC addresses that belong to
        the node.
    :param domain: The domain the node should join.
    :param hostname: the desired hostname for the new node
    """
    # Check that there isn't already a node with one of our MAC
    # addresses, and bail out early if there is.
    nodes = Node.objects.filter(
        current_config__interface__mac_address__in=mac_addresses
    )
    if nodes.exists():
        raise NodeAlreadyExists(
            "One of the MACs %s is already in use by a node." % mac_addresses
        )

    # It is possible that the enlistment code did not provide a subarchitecture
    # for the give architecture; assume 'generic'.
    if "/" not in architecture:
        architecture += "/generic"

    data = {
        "power_type": power_type,
        "power_parameters": power_parameters,
        "architecture": architecture,
        "mac_addresses": mac_addresses,
    }

    if domain is not None:
        data["domain"] = domain

    if hostname is not None:
        data["hostname"] = hostname.strip()

    data_query_dict = get_overridden_query_dict(
        {}, data, AdminMachineWithMACAddressesForm.Meta.fields
    )
    form = AdminMachineWithMACAddressesForm(data_query_dict)
    if form.is_valid():
        node = form.save()
        return node
    else:
        raise ValidationError(form.errors)


@synchronous
@transactional
def commission_node(system_id, user):
    """Request a `Node` with given MAC Address and return it.

    :param system_id: system_id of node to commission.
    :param user: user of the node to commission.
    """
    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        raise NoSuchNode.from_system_id(system_id)
    try:
        node.start_commissioning(User.objects.get(username=user))
    except Exception as e:
        # Cluster takes care of logging
        raise CommissionNodeFailed(e)


@synchronous
@transactional
def request_node_info_by_mac_address(mac_address):
    """Request a `Node` with given MAC Address and return it.

    :param mac_addresses: MAC Address of node to request information
        from.
    """
    try:
        node = (
            PhysicalInterface.objects.prefetch_related("node_config__node")
            .get(mac_address=mac_address)
            .node_config.node
        )
    except PhysicalInterface.DoesNotExist:
        raise NoSuchNode.from_mac_address(mac_address)
    return (node, node.get_boot_purpose())


@synchronous
@transactional
def get_controller_type(system_id: str) -> dict[str, bool]:
    """Get the type of the node specified by its system identifier.

    :param system_id: system_id of node.
    :return: See `GetControllerType`.
    """
    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        raise NoSuchNode.from_system_id(system_id)
    else:
        return {
            "is_region": node.is_region_controller,
            "is_rack": node.is_rack_controller,
        }


@synchronous
@transactional
def get_time_configuration(system_id: str) -> dict[str, frozenset]:
    """Get settings to use for configuring NTP for the given node.

    :param system_id: system_id of node.
    :return: See `GetTimeConfiguration`.
    """
    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        raise NoSuchNode.from_system_id(system_id)
    else:
        return {
            "servers": ntp.get_servers_for(node),
            "peers": ntp.get_peers_for(node),
        }
