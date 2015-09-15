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

from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.enum import (
    INTERFACE_TYPE,
    NODE_PERMISSION,
)
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms_interface import (
    BondInterfaceForm,
    InterfaceForm,
    PhysicalInterfaceForm,
    VLANInterfaceForm,
)
from maasserver.forms_interface_link import (
    InterfaceLinkForm,
    InterfaceUnlinkForm,
)
from maasserver.models.interface import (
    BondInterface,
    Interface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.models.node import Node
from piston.utils import rc


MISSING_FIELD = "This field is required."

BLANK_FIELD = "This field cannot be blank."

DISPLAYED_INTERFACE_FIELDS = (
    'id',
    'name',
    'type',
    'vlan',
    'mac_address',
    'parents',
    'children',
    'tags',
    'enabled',
    'links',
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
        return node.interface_set.all()

    @operation(idempotent=False)
    def create_physical(self, request, system_id):
        """Create a physical interface on node.

        :param name: Name of the interface.
        :param mac_address: MAC address of the interface.
        :param tags: Tags for the interface.
        :param vlan: Untagged VLAN the interface is connected to.

        Returns 404 if the node is not found.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.ADMIN)
        form = PhysicalInterfaceForm(node=node, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            # The Interface model validation is so strict that it will cause
            # the mac_address field to include two messages about it being
            # required. We clean up this response to not provide duplicate
            # information.
            if "mac_address" in form.errors:
                if (MISSING_FIELD in form.errors["mac_address"] and
                        BLANK_FIELD in form.errors["mac_address"]):
                    form.errors["mac_address"].remove(BLANK_FIELD)
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def create_bond(self, request, system_id):
        """Create a bond interface on node.

        :param name: Name of the interface.
        :param mac_address: MAC address of the interface.
        :param tags: Tags for the interface.
        :param vlan: VLAN the interface is connected to.
        :param parents: Parent interfaces that make this bond.

        Returns 404 if the node is not found.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.ADMIN)
        form = BondInterfaceForm(node=node, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def create_vlan(self, request, system_id):
        """Create a VLAN interface on node.

        :param tags: Tags for the interface.
        :param vlan: Tagged VLAN the interface is connected to.
        :param parent: Parent interface for this VLAN interface.

        Returns 404 if the node is not found.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.ADMIN)
        # Cast parent to parents to make it easier on the user and to make it
        # work with the form.
        request.data = request.data.copy()
        if 'parent' in request.data:
            request.data['parents'] = request.data['parent']
        form = VLANInterfaceForm(node=node, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            # Replace parents with parent so it matches the API parameter.
            if 'parents' in form.errors:
                form.errors['parent'] = form.errors.pop('parents')
            raise MAASAPIValidationError(form.errors)


class NodeInterfaceHandler(OperationsHandler):
    """Manage a node's interface."""
    api_doc_section_name = "Node Interface"
    create = None
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
        if interface.mac_address is not None:
            return "%s" % interface.mac_address
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

    @classmethod
    def links(cls, interface):
        return interface.get_links()

    def read(self, request, system_id, interface_id):
        """Read interface on node.

        Returns 404 if the node or interface is not found.
        """
        return Interface.objects.get_interface_or_404(
            system_id, interface_id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, system_id, interface_id):
        """Update interface on node.

        Fields for physical interface:
        :param name: Name of the interface.
        :param mac_address: MAC address of the interface.
        :param tags: Tags for the interface.
        :param vlan: Untagged VLAN the interface is connected to.

        Fields for bond interface:
        :param name: Name of the interface.
        :param mac_address: MAC address of the interface.
        :param tags: Tags for the interface.
        :param vlan: Tagged VLAN the interface is connected to.
        :param parents: Parent interfaces that make this bond.

        Fields for VLAN interface:
        :param tags: Tags for the interface.
        :param vlan: VLAN the interface is connected to.
        :param parent: Parent interface for this VLAN interface.

        Returns 404 if the node or interface is not found.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, interface_id, request.user, NODE_PERMISSION.ADMIN)
        interface_form = InterfaceForm.get_interface_form(interface.type)
        # For VLAN interface we cast parents to parent. As a VLAN can only
        # have one parent.
        if interface.type == INTERFACE_TYPE.VLAN:
            request.data = request.data.copy()
            if 'parent' in request.data:
                request.data['parents'] = request.data['parent']
        form = interface_form(instance=interface, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            # Replace parents with parent so it matches the API parameter, if
            # the interface being editted was a VLAN interface.
            if (interface.type == INTERFACE_TYPE.VLAN and
                    'parents' in form.errors):
                form.errors['parent'] = form.errors.pop('parents')
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, system_id, interface_id):
        """Delete interface on node.

        Returns 404 if the node or interface is not found.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, interface_id, request.user, NODE_PERMISSION.ADMIN)
        interface.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def link_subnet(self, request, system_id, interface_id):
        """Link interface to a subnet.

        :param mode: AUTO, DHCP, STATIC or LINK_UP connection to subnet.
        :param subnet: Subnet linked to interface.
        :param ip_address: IP address for the interface in subnet. Only used
            when mode is STATIC. If not provided an IP address from subnet
            will be auto selected.

        Mode definitions:
        AUTO - Assign this interface a static IP address from the provided
        subnet. The subnet must be a managed subnet. The IP address will
        not be assigned until the node goes to be deployed.

        DHCP - Bring this interface up with DHCP on the given subnet. Only
        one subnet can be set to DHCP. If the subnet is managed this
        interface will pull from the dynamic IP range.

        STATIC - Bring this interface up with a STATIC IP address on the
        given subnet. Any number of STATIC links can exist on an interface.

        LINK_UP - Bring this interface up only on the given subnet. No IP
        address will be assigned to this interface. The interface cannot
        have any current AUTO, DHCP or STATIC links.

        Returns 404 if the node or interface is not found.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, interface_id, request.user, NODE_PERMISSION.ADMIN)
        form = InterfaceLinkForm(instance=interface, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def unlink_subnet(self, request, system_id, interface_id):
        """Unlink interface to a subnet.

        :param id: ID of the link on the interface to remove.

        Returns 404 if the node or interface is not found.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, interface_id, request.user, NODE_PERMISSION.ADMIN)
        form = InterfaceUnlinkForm(instance=interface, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


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
