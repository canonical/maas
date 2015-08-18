# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Interface`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from maasserver.api.support import OperationsHandler
from maasserver.enum import NODE_PERMISSION
from maasserver.models.interface import (
    BondInterface,
    Interface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.models.node import Node
from piston.utils import rc


DISPLAYED_INTERFACE_FIELDS = (
    'id',
    'name',
    'type',
    'vlan',
    'mac_address',
    'parents',
    'children',
    'tags',
)


class NodeInterfacesHandler(OperationsHandler):
    """Manage interfaces on a node."""
    api_doc_section_name = "Node Interfaces"
    create = update = delete = None
    fields = DISPLAYED_INTERFACE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('node_interfaces_handler', ["system_id"])

    def read(self, request, system_id):
        """List all interfaces belonging to node.

        Returns 404 if the node is not found.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.VIEW)
        return Interface.objects.get_interfaces_for_node(node)


class NodeInterfaceHandler(OperationsHandler):
    """Manage a node's interface."""
    api_doc_section_name = "Node Interface"
    create = update = None
    model = Interface
    fields = DISPLAYED_INTERFACE_FIELDS

    @classmethod
    def resource_uri(cls, interface=None):
        # See the comment in NodeHandler.resource_uri.
        system_id = "system_id"
        interface_id = "interface_id"
        if interface is not None:
            interface_id = interface.id
            node = interface.get_node()
            if node is not None:
                system_id = node.system_id
        return ('node_interface_handler', (system_id, interface_id))

    @classmethod
    def mac_address(cls, interface):
        if interface.mac is not None:
            return "%s" % interface.mac.mac_address
        else:
            return None

    @classmethod
    def parents(cls, interface):
        return sorted(
            nic.name
            for nic in interface.parents.all()
        )

    @classmethod
    def children(cls, interface):
        return sorted(
            nic.child.name
            for nic in interface.children_relationships.all()
        )

    def read(self, request, system_id, interface_id):
        """Read interface on node.

        Returns 404 if the node or interface is not found.
        """
        return Interface.objects.get_interface_or_404(
            system_id, interface_id, request.user, NODE_PERMISSION.VIEW)

    def delete(self, request, system_id, interface_id):
        """Delete interface on node.

        Returns 404 if the node or interface is not found.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, interface_id, request.user, NODE_PERMISSION.ADMIN)
        interface.delete()
        return rc.DELETED


class PhysicalInterfaceHandler(NodeInterfaceHandler):
    """
    This handler only exists because piston requires a unique handler per
    class type. Without this class the resource_uri will not be added to any
    object that is of type `PhysicalInterface` when it is emitted from the
    `NodeInterfaceHandler`.

    Important: This should not be used in the urls_api.py. This is only here
        to support piston.
    """
    hidden = True
    model = PhysicalInterface


class BondInterfaceHandler(NodeInterfaceHandler):
    """
    This handler only exists because piston requires a unique handler per
    class type. Without this class the resource_uri will not be added to any
    object that is of type `BondInterface` when it is emitted from the
    `NodeInterfaceHandler`.

    Important: This should not be used in the urls_api.py. This is only here
        to support piston.
    """
    hidden = True
    model = BondInterface


class VLANInterfaceHandler(NodeInterfaceHandler):
    """
    This handler only exists because piston requires a unique handler per
    class type. Without this class the resource_uri will not be added to any
    object that is of type `VLANInterface` when it is emitted from the
    `NodeInterfaceHandler`.

    Important: This should not be used in the urls_api.py. This is only here
        to support piston.
    """
    hidden = True
    model = VLANInterface
