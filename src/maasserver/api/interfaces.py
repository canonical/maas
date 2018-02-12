# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Interface`."""

from django.forms.utils import ErrorList
from formencode.validators import StringBool
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    get_mandatory_param,
    get_optional_param,
)
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.exceptions import (
    MAASAPIForbidden,
    MAASAPIValidationError,
    NodeStateViolation,
)
from maasserver.forms.interface import (
    AcquiredBridgeInterfaceForm,
    BondInterfaceForm,
    BridgeInterfaceForm,
    ControllerInterfaceForm,
    DeployedInterfaceForm,
    InterfaceForm,
    PhysicalInterfaceForm,
    VLANInterfaceForm,
)
from maasserver.forms.interface_link import (
    InterfaceLinkForm,
    InterfaceSetDefaultGatwayForm,
    InterfaceUnlinkForm,
)
from maasserver.models import (
    Machine,
    Node,
)
from maasserver.models.interface import (
    BondInterface,
    BridgeInterface,
    Interface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.utils.orm import prefetch_queryset
from piston3.utils import rc


MISSING_FIELD = "This field is required."

BLANK_FIELD = "This field cannot be blank."

DISPLAYED_INTERFACE_FIELDS = (
    'system_id',
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
    'params',
    'discovered',
    'effective_mtu',
    'vendor',
    'product',
    'firmware_version',
)

INTERFACES_PREFETCH = [
    'vlan__primary_rack',
    'vlan__secondary_rack',
    'vlan__fabric__vlan_set',
    'vlan__space',
    'parents',
    'ip_addresses__subnet',
    # Prefetch 3 levels deep, anything more will require extra queries.
    'children_relationships__child__vlan',
    ('children_relationships__child__'
     'children_relationships__child__vlan'),
    ('children_relationships__child__'
     'children_relationships__child__'
     'children_relationships__child__vlan'),
]

ALLOWED_STATES = (NODE_STATUS.READY, NODE_STATUS.ALLOCATED, NODE_STATUS.BROKEN)


def raise_error_for_invalid_state_on_allocated_operations(
        node, user, operation, extra_states=None):
    """Raises `NodeStateViolation` when the status of the node is not
    READY or BROKEN.

    :param node: Node to check status.
    :param user: User performing the operation.
    :param operation: Nice name of the operation.
    :param extra_states: Extra states that the node can be in when checking
        the status of the node.
    :type extra_states: `Iterable`.
    """
    allowed = list(ALLOWED_STATES)
    if extra_states is not None:
        allowed.extend(extra_states)
    if node.status not in allowed:
        raise NodeStateViolation(
            "Cannot %s interface because the machine is not Ready, Allocated, "
            "or Broken." % operation)


def raise_error_if_controller(node, operation):
    if node.is_controller:
        raise MAASAPIForbidden(
            "Cannot %s interface on a controller." % operation)


class InterfacesHandler(OperationsHandler):
    """Manage interfaces on a node."""
    api_doc_section_name = "Interfaces"
    create = update = delete = None
    fields = DISPLAYED_INTERFACE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('interfaces_handler', ["system_id"])

    def read(self, request, system_id):
        """List all interfaces belonging to a machine, device, or
        rack controller.

        Returns 404 if the node is not found.
        """
        node = Node.objects.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.VIEW)
        interfaces = prefetch_queryset(
            node.interface_set.all(), INTERFACES_PREFETCH)
        # Preload the node on the interface, no need for another query.
        for interface in interfaces:
            interface.node = node
        return interfaces

    @operation(idempotent=False)
    def create_physical(self, request, system_id):
        """Create a physical interface on a machine and device.

        :param name: Name of the interface.
        :param mac_address: MAC address of the interface.
        :param tags: Tags for the interface.
        :param vlan: Untagged VLAN the interface is connected to.  If not
            provided then the interface is considered disconnected.

        Following are extra parameters that can be set on the interface:

        :param mtu: Maximum transmission unit.
        :param accept_ra: Accept router advertisements. (IPv6 only)
        :param autoconf: Perform stateless autoconfiguration. (IPv6 only)

        Returns 404 if the node is not found.
        """
        node = Node.objects.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.EDIT)
        raise_error_if_controller(node, "create")
        # Machine type nodes require the node needs to be in the correct state.
        if node.node_type == NODE_TYPE.MACHINE:
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "create")
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
                    form.errors["mac_address"] = ErrorList([
                        error
                        for error in form.errors["mac_address"]
                        if error != BLANK_FIELD
                    ])
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def create_bond(self, request, system_id):
        """Create a bond interface on a machine.

        :param name: Name of the interface.
        :param mac_address: MAC address of the interface.
        :param tags: Tags for the interface.
        :param vlan: VLAN the interface is connected to.  If not
            provided then the interface is considered disconnected.
        :param parents: Parent interfaces that make this bond.

        Following are parameters specific to bonds:

        :param bond_mode: The operating mode of the bond.
            (Default: active-backup).
        :param bond_miimon: The link monitoring freqeuncy in milliseconds.
            (Default: 100).
        :param bond_downdelay: Specifies the time, in milliseconds, to wait
            before disabling a slave after a link failure has been detected.
        :param bond_updelay: Specifies the time, in milliseconds, to wait
            before enabling a slave after a link recovery has been detected.
        :param bond_lacp_rate: Option specifying the rate in which we'll ask
            our link partner to transmit LACPDU packets in 802.3ad mode.
            Available options are fast or slow. (Default: slow).
        :param bond_xmit_hash_policy: The transmit hash policy to use for
            slave selection in balance-xor, 802.3ad, and tlb modes.
            (Default: layer2)
        :param bond_num_grat_arp: The number of peer notifications (IPv4 ARP
            or IPv6 Neighbour Advertisements) to be issued after a failover.
            (Default: 1)

        Supported bonding modes (bond-mode):
        balance-rr - Transmit packets in sequential order from the first
        available slave through the last.  This mode provides load balancing
        and fault tolerance.

        active-backup - Only one slave in the bond is active.  A different
        slave becomes active if, and only if, the active slave fails.  The
        bond's MAC address is externally visible on only one port (network
        adapter) to avoid confusing the switch.

        balance-xor - Transmit based on the selected transmit hash policy.
        The default policy is a simple [(source MAC address XOR'd with
        destination MAC address XOR packet type ID) modulo slave count].

        broadcast - Transmits everything on all slave interfaces. This mode
        provides fault tolerance.

        802.3ad - IEEE 802.3ad Dynamic link aggregation.  Creates aggregation
        groups that share the same speed and duplex settings.  Utilizes all
        slaves in the active aggregator according to the 802.3ad specification.

        balance-tlb - Adaptive transmit load balancing: channel bonding that
        does not require any special switch support.

        balance-alb - Adaptive load balancing: includes balance-tlb plus
        receive load balancing (rlb) for IPV4 traffic, and does not require any
        special switch support.  The receive load balancing is achieved by
        ARP negotiation.

        Following are extra parameters that can be set on the interface:

        :param mtu: Maximum transmission unit.
        :param accept_ra: Accept router advertisements. (IPv6 only)
        :param autoconf: Perform stateless autoconfiguration. (IPv6 only)

        Returns 404 if the node is not found.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.ADMIN)
        raise_error_for_invalid_state_on_allocated_operations(
            machine, request.user, "create bond")
        form = BondInterfaceForm(node=machine, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def create_vlan(self, request, system_id):
        """Create a VLAN interface on a machine.

        :param tags: Tags for the interface.
        :param vlan: Tagged VLAN the interface is connected to.
        :param parent: Parent interface for this VLAN interface.

        Following are extra parameters that can be set on the interface:

        :param mtu: Maximum transmission unit.
        :param accept_ra: Accept router advertisements. (IPv6 only)
        :param autoconf: Perform stateless autoconfiguration. (IPv6 only)

        Returns 404 if the node is not found.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.ADMIN)
        raise_error_for_invalid_state_on_allocated_operations(
            machine, request.user, "create VLAN")
        # Cast parent to parents to make it easier on the user and to make it
        # work with the form.
        request.data = request.data.copy()
        if 'parent' in request.data:
            request.data['parents'] = request.data['parent']
        form = VLANInterfaceForm(node=machine, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            # Replace parents with parent so it matches the API parameter.
            if 'parents' in form.errors:
                form.errors['parent'] = form.errors.pop('parents')
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def create_bridge(self, request, system_id):
        """Create a bridge interface on a machine.

        :param name: Name of the interface.
        :param mac_address: MAC address of the interface.
        :param tags: Tags for the interface.
        :param vlan: VLAN the interface is connected to.
        :param parent: Parent interface for this bridge interface.

        Following are parameters specific to bridges:

        :param bridge_stp: Turn spanning tree protocol on or off.
            (Default: False).
        :param bridge_fd: Set bridge forward delay to time seconds.
            (Default: 15).

        Following are extra parameters that can be set on the interface:

        :param mtu: Maximum transmission unit.
        :param accept_ra: Accept router advertisements. (IPv6 only)
        :param autoconf: Perform stateless autoconfiguration. (IPv6 only)

        Returns 404 if the node is not found.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.EDIT)
        raise_error_for_invalid_state_on_allocated_operations(
            machine, request.user, "create bridge")
        # Cast parent to parents to make it easier on the user and to make it
        # work with the form.
        request.data = request.data.copy()
        if 'parent' in request.data:
            request.data['parents'] = request.data['parent']
        if machine.status == NODE_STATUS.ALLOCATED:
            form = AcquiredBridgeInterfaceForm(
                node=machine, data=request.data)
        else:
            form = BridgeInterfaceForm(node=machine, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            # Replace parents with parent so it matches the API parameter.
            if 'parents' in form.errors:
                form.errors['parent'] = form.errors.pop('parents')
            raise MAASAPIValidationError(form.errors)


class InterfaceHandler(OperationsHandler):
    """Manage a node's or device's interface."""
    api_doc_section_name = "Interface"
    create = None
    model = Interface
    fields = DISPLAYED_INTERFACE_FIELDS

    @classmethod
    def resource_uri(cls, interface=None):
        # See the comment in NodeHandler.resource_uri.
        system_id = "system_id"
        interface_id = "id"
        if interface is not None:
            interface_id = interface.id
            node = interface.get_node()
            if node is not None:
                system_id = node.system_id
        return ('interface_handler', (system_id, interface_id))

    @classmethod
    def system_id(cls, interface):
        node = interface.get_node()
        return None if node is None else node.system_id

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

    @classmethod
    def discovered(cls, interface):
        return interface.get_discovered()

    @classmethod
    def effective_mtu(cls, interface):
        return interface.get_effective_mtu()

    def read(self, request, system_id, id):
        """Read interface on node.

        Returns 404 if the node or interface is not found.
        """
        return Interface.objects.get_interface_or_404(
            system_id, id, request.user, NODE_PERMISSION.VIEW)

    def update(self, request, system_id, id):
        """Update interface on node.

        Machines must have a status of Ready or Broken to have access to all
        options. Machines with Deployed status can only have the name and/or
        mac_address updated for an interface. This is intented to allow a bad
        interface to be replaced while the machine remains deployed.

        Fields for physical interface:

        :param name: Name of the interface.
        :param mac_address: MAC address of the interface.
        :param tags: Tags for the interface.
        :param vlan: Untagged VLAN the interface is connected to.  If not set
            then the interface is considered disconnected.

        Fields for bond interface:

        :param name: Name of the interface.
        :param mac_address: MAC address of the interface.
        :param tags: Tags for the interface.
        :param vlan: Untagged VLAN the interface is connected to.  If not set
            then the interface is considered disconnected.
        :param parents: Parent interfaces that make this bond.

        Fields for VLAN interface:

        :param tags: Tags for the interface.
        :param vlan: Tagged VLAN the interface is connected to.
        :param parent: Parent interface for this VLAN interface.

        Fields for bridge interface:

        :param name: Name of the interface.
        :param mac_address: MAC address of the interface.
        :param tags: Tags for the interface.
        :param vlan: VLAN the interface is connected to.
        :param parent: Parent interface for this bridge interface.

        Following are extra parameters that can be set on all interface types:

        :param mtu: Maximum transmission unit.
        :param accept_ra: Accept router advertisements. (IPv6 only)
        :param autoconf: Perform stateless autoconfiguration. (IPv6 only)

        Following are parameters specific to bonds:

        :param bond_mode: The operating mode of the bond.
            (Default: active-backup).
        :param bond_miimon: The link monitoring freqeuncy in milliseconds.
            (Default: 100).
        :param bond_downdelay: Specifies the time, in milliseconds, to wait
            before disabling a slave after a link failure has been detected.
        :param bond_updelay: Specifies the time, in milliseconds, to wait
            before enabling a slave after a link recovery has been detected.
        :param bond_lacp_rate: Option specifying the rate in which we'll ask
            our link partner to transmit LACPDU packets in 802.3ad mode.
            Available options are fast or slow. (Default: slow).
        :param bond_xmit_hash_policy: The transmit hash policy to use for
            slave selection in balance-xor, 802.3ad, and tlb modes.

        Supported bonding modes (bond-mode):

        balance-rr - Transmit packets in sequential order from the first
        available slave through the last.  This mode provides load balancing
        and fault tolerance.

        active-backup - Only one slave in the bond is active.  A different
        slave becomes active if, and only if, the active slave fails.  The
        bond's MAC address is externally visible on only one port (network
        adapter) to avoid confusing the switch.

        balance-xor - Transmit based on the selected transmit hash policy.
        The default policy is a simple [(source MAC address XOR'd with
        destination MAC address XOR packet type ID) modulo slave count].

        broadcast - Transmits everything on all slave interfaces. This mode
        provides fault tolerance.

        802.3ad - IEEE 802.3ad Dynamic link aggregation.  Creates aggregation
        groups that share the same speed and duplex settings.  Utilizes all
        slaves in the active aggregator according to the 802.3ad specification.

        balance-tlb - Adaptive transmit load balancing: channel bonding that
        does not require any special switch support.

        balance-alb - Adaptive load balancing: includes balance-tlb plus
        receive load balancing (rlb) for IPV4 traffic, and does not require any
        special switch support.  The receive load balancing is achieved by
        ARP negotiation.

        Following are parameters specific to bridges:

        :param bridge_stp: Turn spanning tree protocol on or off.
            (Default: False).
        :param bridge_fd: Set bridge forward delay to time seconds.
            (Default: 15).

        Returns 404 if the node or interface is not found.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, id, request.user, NODE_PERMISSION.EDIT)
        node = interface.get_node()
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "update interface",
                extra_states=[NODE_STATUS.DEPLOYED])
        if node.is_controller:
            if interface.type == INTERFACE_TYPE.VLAN:
                raise MAASAPIForbidden(
                    "Cannot modify VLAN interface on controller.")
            interface_form = ControllerInterfaceForm
        elif node.status == NODE_STATUS.DEPLOYED:
            interface_form = DeployedInterfaceForm
        else:
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

    def delete(self, request, system_id, id):
        """Delete interface on node.

        Returns 404 if the node or interface is not found.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, id, request.user, NODE_PERMISSION.EDIT)
        node = interface.get_node()
        raise_error_if_controller(node, "delete interface")
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                interface.node, request.user, "delete interface")
        interface.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def link_subnet(self, request, system_id, id):
        """Link interface to a subnet.

        :param mode: AUTO, DHCP, STATIC or LINK_UP connection to subnet.
        :param subnet: Subnet linked to interface.
        :param ip_address: IP address for the interface in subnet. Only used
            when mode is STATIC. If not provided an IP address from subnet
            will be auto selected.
        :param force: If True, allows LINK_UP to be set on the interface
            even if other links already exist. Also allows the selection of any
            VLAN, even a VLAN MAAS does not believe the interface to currently
            be on. Using this option will cause all other links on the
            interface to be deleted. (Defaults to False.)
        :param default_gateway: True sets the gateway IP address for the subnet
            as the default gateway for the node this interface belongs to.
            Option can only be used with the AUTO and STATIC modes.

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
        force = get_optional_param(
            request.POST, 'force', default=False, validator=StringBool)
        interface = Interface.objects.get_interface_or_404(
            system_id, id, request.user, NODE_PERMISSION.EDIT)
        node = interface.get_node()
        raise_error_if_controller(node, "link subnet")
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "link subnet")
            allowed_modes = [
                INTERFACE_LINK_TYPE.AUTO,
                INTERFACE_LINK_TYPE.DHCP,
                INTERFACE_LINK_TYPE.STATIC,
                INTERFACE_LINK_TYPE.LINK_UP,
            ]
        else:
            # Devices can only be set in static IP mode.
            allowed_modes = [INTERFACE_LINK_TYPE.STATIC]
        form = InterfaceLinkForm(
            instance=interface, data=request.data, allowed_modes=allowed_modes,
            force=force)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def disconnect(self, request, system_id, id):
        """Disconnect an interface.

        Deletes any linked subnets and IP addresses, and disconnects the
        interface from any associated VLAN.

        Returns 404 if the node or interface is not found.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, id, request.user, NODE_PERMISSION.EDIT)
        node = interface.get_node()
        raise_error_if_controller(node, "disconnect")
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "disconnect")
        interface.ip_addresses.all().delete()
        interface.vlan = None
        interface.save()
        return interface

    @operation(idempotent=False)
    def unlink_subnet(self, request, system_id, id):
        """Unlink interface to a subnet.

        :param id: ID of the link on the interface to remove.

        Returns 404 if the node or interface is not found.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, id, request.user, NODE_PERMISSION.EDIT)
        node = interface.get_node()
        raise_error_if_controller(node, "link subnet")
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "unlink subnet")
        form = InterfaceUnlinkForm(instance=interface, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def set_default_gateway(self, request, system_id, id):
        """Set the node to use this interface as the default gateway.

        If this interface has more than one subnet with a gateway IP in the
        same IP address family then specifying the ID of the link on
        this interface is required.

        :param link_id: ID of the link on this interface to select the
            default gateway IP address from.

        Returns 400 if the interface has not AUTO or STATIC links.
        Returns 404 if the node or interface is not found.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, id, request.user, NODE_PERMISSION.EDIT)
        node = interface.get_node()
        raise_error_if_controller(node, "link subnet")
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "set default gateway")
        form = InterfaceSetDefaultGatwayForm(
            instance=interface, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def add_tag(self, request, system_id, id):
        """Add a tag to interface on a node.

        :param tag: The tag being added.

        Returns 404 if the node or interface is not found.
        Returns 403 if the user is not allowed to update the interface.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, id, request.user, NODE_PERMISSION.EDIT)
        interface.add_tag(get_mandatory_param(request.POST, 'tag'))
        interface.save()
        return interface

    @operation(idempotent=False)
    def remove_tag(self, request, system_id, id):
        """Remove a tag from interface on a node.

        :param tag: The tag being removed.

        Returns 404 if the node or interface is not found.
        Returns 403 if the user is not allowed to update the interface.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id, id, request.user, NODE_PERMISSION.EDIT)
        interface.remove_tag(get_mandatory_param(request.POST, 'tag'))
        interface.save()
        return interface


class PhysicaInterfaceHandler(InterfaceHandler):
    """
    This handler only exists because piston requires a unique handler per
    class type. Without this class the resource_uri will not be added to any
    object that is of type `PhysicalInterface` when it is emitted from the
    `InterfaceHandler`.

    Important: This should not be used in the urls_api.py. This is only here
        to support piston.
    """
    hidden = True
    model = PhysicalInterface


class BondInterfaceHandler(InterfaceHandler):
    """
    This handler only exists because piston requires a unique handler per
    class type. Without this class the resource_uri will not be added to any
    object that is of type `BondInterface` when it is emitted from the
    `InterfaceHandler`.

    Important: This should not be used in the urls_api.py. This is only here
        to support piston.
    """
    hidden = True
    model = BondInterface


class VLANInterfaceHandler(InterfaceHandler):
    """
    This handler only exists because piston requires a unique handler per
    class type. Without this class the resource_uri will not be added to any
    object that is of type `VLANInterface` when it is emitted from the
    `InterfaceHandler`.

    Important: This should not be used in the urls_api.py. This is only here
        to support piston.
    """
    hidden = True
    model = VLANInterface


class BridgeInterfaceHandler(InterfaceHandler):
    """
    This handler only exists because piston requires a unique handler per
    class type. Without this class the resource_uri will not be added to any
    object that is of type `BridgeInterface` when it is emitted from the
    `InterfaceHandler`.

    Important: This should not be used in the urls_api.py. This is only here
        to support piston.
    """
    hidden = True
    model = BridgeInterface
