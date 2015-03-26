# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to nodes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "mark_node_failed",
    "update_node_power_state",
    "commission_node",
    "create_node",
]

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from maasserver import exceptions
from maasserver.api.utils import get_overridden_query_dict
from maasserver.enum import NODE_STATUS
from maasserver.forms import AdminNodeWithMACAddressesForm
from maasserver.models import (
    MACAddress,
    Node,
    NodeGroup,
)
from maasserver.utils.orm import transactional
from provisioningserver.rpc.exceptions import (
    CommissionNodeFailed,
    NodeAlreadyExists,
    NodeStateViolation,
    NoSuchCluster,
    NoSuchNode,
)
from provisioningserver.utils.twisted import synchronous
import simplejson as json


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
        node.mark_failed(error_description)
    except exceptions.NodeStateViolation as e:
        raise NodeStateViolation(e)


@synchronous
@transactional
def list_cluster_nodes_power_parameters(uuid):
    """Query a cluster controller and return all of its nodes
    power parameters

    for :py:class:`~provisioningserver.rpc.region.ListNodePowerParameters`.
    """
    try:
        nodegroup = NodeGroup.objects.get_by_natural_key(uuid)
    except NodeGroup.DoesNotExist:
        raise NoSuchCluster.from_uuid(uuid)
    else:
        power_info_by_node = (
            (node, node.get_effective_power_info())
            for node in nodegroup.node_set.exclude(status=NODE_STATUS.BROKEN)
        )
        return [
            {
                'system_id': node.system_id,
                'hostname': node.hostname,
                'power_state': node.power_state,
                'power_type': power_info.power_type,
                'context': power_info.power_parameters,
            }
            for node, power_info in power_info_by_node
            if power_info.power_type is not None
        ]


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
def create_node(cluster_uuid, architecture, power_type,
                power_parameters, mac_addresses, hostname=None):
    """Create a new `Node` and return it.

    :param cluster_uuid: The UUID of the cluster upon which the node
        should be created.
    :param architecture: The architecture of the new node.
    :param power_type: The power type of the new node.
    :param power_parameters: A JSON-encoded string of power parameters
        for the new node.
    :param mac_addresses: An iterable of MAC addresses that belong to
        the node.
    :param hostname: the desired hostname for the new node
    """
    # Check that there isn't already a node with one of our MAC
    # addresses, and bail out early if there is.
    nodes = Node.objects.filter(macaddress__mac_address__in=mac_addresses)
    if nodes.count() > 0:
        raise NodeAlreadyExists(
            "One of the MACs %s is already in use by a node." %
            mac_addresses)

    # It is possible that the enlistment code did not provide a subarchitecture
    # for the give architecture; assume 'generic'.
    if '/' not in architecture:
        architecture = '%s/generic' % architecture

    cluster = NodeGroup.objects.get_by_natural_key(cluster_uuid)
    data = {
        'power_type': power_type,
        'power_parameters': power_parameters,
        'architecture': architecture,
        'nodegroup': cluster,
        'mac_addresses': mac_addresses,
    }

    if hostname is not None:
        data['hostname'] = hostname.strip()

    data_query_dict = get_overridden_query_dict(
        {}, data, AdminNodeWithMACAddressesForm.Meta.fields)
    form = AdminNodeWithMACAddressesForm(data_query_dict)
    if form.is_valid():
        node = form.save()
        # We have to explicitly save the power parameters; the form
        # won't do it for us.
        node.power_parameters = json.loads(power_parameters)
        node.save()
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
        node.start_commissioning(
            User.objects.get(username=user))
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
        node = MACAddress.objects.get(mac_address=mac_address).node
    except MACAddress.DoesNotExist:
        raise NoSuchNode.from_mac_address(mac_address)
    return (node, node.get_boot_purpose())
