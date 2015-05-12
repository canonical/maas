# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `NodeMac`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'NodeMacHandler',
    'NodeMacsHandler',
    ]


from django.shortcuts import get_object_or_404
from maasserver.api.support import OperationsHandler
from maasserver.enum import NODE_PERMISSION
from maasserver.fields import validate_mac
from maasserver.models import (
    MACAddress,
    Node,
)
from piston.utils import rc


class NodeMacsHandler(OperationsHandler):
    """Manage MAC addresses for a given Node.

    This is where you manage the MAC addresses linked to a Node, including
    associating a new MAC address with the Node.

    The Node is identified by its system_id.
    """
    api_doc_section_name = "Node MAC addresses"
    update = delete = None

    def read(self, request, system_id):
        """Read all MAC addresses related to a Node.

        Returns 404 if the node is not found.
        """
        node = Node.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.VIEW)

        return MACAddress.objects.filter(node=node).order_by('id')

    def create(self, request, system_id):
        """Create a MAC address for a specified Node.

        Returns 404 if the node is not found.
        """
        node = Node.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.EDIT)
        mac = node.add_mac_address(request.data.get('mac_address', None))
        return mac

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('node_macs_handler', ['system_id'])


class NodeMacHandler(OperationsHandler):
    """Manage a Node MAC address.

    The MAC address object is identified by the system_id for the Node it
    is attached to, plus the MAC address itself.
    """
    api_doc_section_name = "Node MAC address"
    create = update = None
    fields = ('mac_address',)
    model = MACAddress

    def read(self, request, system_id, mac_address):
        """Read a MAC address related to a Node.

        Returns 404 if the node or the MAC address is not found.
        """
        node = Node.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.VIEW)

        validate_mac(mac_address)
        return get_object_or_404(
            MACAddress, node=node, mac_address=mac_address)

    def delete(self, request, system_id, mac_address):
        """Delete a specific MAC address for the specified Node.

        Returns 404 if the node or the MAC address is not found.
        Returns 204 after the MAC address is successfully deleted.
        """
        validate_mac(mac_address)
        node = Node.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.EDIT)

        mac = get_object_or_404(MACAddress, node=node, mac_address=mac_address)
        mac.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, mac=None):
        node_system_id = "system_id"
        mac_address = "mac_address"
        if mac is not None:
            node_system_id = mac.node.system_id
            mac_address = mac.mac_address
        return ('node_mac_handler', [node_system_id, mac_address])
