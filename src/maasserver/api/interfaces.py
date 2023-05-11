# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Interface`."""

from django.forms.utils import ErrorList
from formencode.validators import StringBool
from piston3.utils import rc

from maasserver.api.support import operation, OperationsHandler
from maasserver.api.utils import get_mandatory_param, get_optional_param
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
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
from maasserver.models import Machine, Node
from maasserver.models.interface import (
    BondInterface,
    BridgeInterface,
    Interface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.permissions import NodePermission
from maasserver.utils.orm import prefetch_queryset

MISSING_FIELD = "This field is required."

BLANK_FIELD = "This field cannot be blank."

DISPLAYED_INTERFACE_FIELDS = (
    "system_id",
    "id",
    "name",
    "type",
    "vlan",
    "mac_address",
    "parents",
    "children",
    "tags",
    "enabled",
    "links",
    "params",
    "discovered",
    "effective_mtu",
    "vendor",
    "product",
    "firmware_version",
    "link_connected",
    "interface_speed",
    "link_speed",
    "numa_node",
    "sriov_max_vf",
)

INTERFACES_PREFETCH = [
    "vlan__primary_rack",
    "vlan__secondary_rack",
    "vlan__fabric__vlan_set",
    "vlan__space",
    "numa_node",
    "parents",
    "ip_addresses__subnet",
    # Prefetch 3 levels deep, anything more will require extra queries.
    "children_relationships__child__vlan",
    ("children_relationships__child__" "children_relationships__child__vlan"),
    (
        "children_relationships__child__"
        "children_relationships__child__"
        "children_relationships__child__vlan"
    ),
]

ALLOWED_STATES = (
    NODE_STATUS.NEW,
    NODE_STATUS.READY,
    NODE_STATUS.FAILED_TESTING,
    NODE_STATUS.ALLOCATED,
    NODE_STATUS.BROKEN,
)


def raise_error_for_invalid_state_on_allocated_operations(
    node, user, operation, extra_states=None
):
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
            f"Cannot {operation} interface because the machine is not New, "
            "Ready, Allocated, or Broken."
        )


def raise_error_if_controller(node, operation):
    if node.is_controller:
        raise MAASAPIForbidden(
            "Cannot %s interface on a controller." % operation
        )


class InterfacesHandler(OperationsHandler):
    """Manage interfaces on a node."""

    api_doc_section_name = "Interfaces"
    create = update = delete = None
    fields = DISPLAYED_INTERFACE_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("interfaces_handler", ["system_id"])

    def read(self, request, system_id):
        """@description-title List interfaces
        @description List all interfaces belonging to a machine, device, or
        rack controller.

        @param (string) "{system_id}" [required=true] A system_id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        interface objects.
        @success-example "success-json" [exkey=interfaces-read] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        node = Node.objects.get_node_or_404(
            system_id, request.user, NodePermission.view
        )
        return prefetch_queryset(
            node.current_config.interface_set.all(), INTERFACES_PREFETCH
        )

    @operation(idempotent=False)
    def create_physical(self, request, system_id):
        """@description-title Create a physical interface
        @description Create a physical interface on a machine and device.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (string) "name" [required=false] Name of the interface.

        @param (string) "mac_address" [required=true] MAC address of the
        interface.

        @param (string) "tags" [required=false] Tags for the interface.

        @param (string) "vlan" [required=false] Untagged VLAN the interface is
        connected to. If not provided then the interface is considered
        disconnected.

        @param (int) "mtu" [required=false] Maximum transmission unit.

        @param (boolean) "accept_ra" [required=false] Accept router
        advertisements. (IPv6 only)

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new
        interface object.
        @success-example "success-json" [exkey=interfaces-create-physical]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Node matches the given query.

        """
        node = Node.objects.get_node_or_404(
            system_id, request.user, NodePermission.edit
        )
        raise_error_if_controller(node, "create")
        # Machine type nodes require the node needs to be in the correct state
        # and that the user has admin permissions.
        if node.node_type == NODE_TYPE.MACHINE:
            if not request.user.has_perm(NodePermission.admin, node):
                raise MAASAPIForbidden()
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "create"
            )
        form = PhysicalInterfaceForm(node=node, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            # The Interface model validation is so strict that it will cause
            # the mac_address field to include two messages about it being
            # required. We clean up this response to not provide duplicate
            # information.
            if "mac_address" in form.errors:
                if (
                    MISSING_FIELD in form.errors["mac_address"]
                    and BLANK_FIELD in form.errors["mac_address"]
                ):
                    form.errors["mac_address"] = ErrorList(
                        [
                            error
                            for error in form.errors["mac_address"]
                            if error != BLANK_FIELD
                        ]
                    )
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def create_bond(self, request, system_id):
        """@description-title Create a bond inteface
        @description Create a bond interface on a machine.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (string) "name" [required=true] Name of the interface.

        @param (string) "mac_address" [required=false] MAC address of the
        interface.

        @param (string) "tags" [required=false] Tags for the interface.

        @param (string) "vlan" [required=false] VLAN the interface is connected
        to. If not provided then the interface is considered disconnected.

        @param (int) "parents" [required=true] Parent interface ids that make
        this bond.

        @param (string) "bond_mode" [required=false,formatting=true] The
        operating mode of the bond.  (Default: active-backup).

        Supported bonding modes:

        - ``balance-rr``: Transmit packets in sequential order from the first
          available slave through the last. This mode provides load balancing
          and fault tolerance.

        - ``active-backup``: Only one slave in the bond is active. A different
          slave becomes active if, and only if, the active slave fails. The
          bond's MAC address is externally visible on only one port (network
          adapter) to avoid confusing the switch.

        - ``balance-xor``: Transmit based on the selected transmit hash policy.
          The default policy is a simple [(source MAC address XOR'd with
          destination MAC address XOR packet type ID) modulo slave count].

        - ``broadcast``: Transmits everything on all slave interfaces. This
          mode provides fault tolerance.

        - ``802.3ad``: IEEE 802.3ad dynamic link aggregation. Creates
          aggregation groups that share the same speed and duplex settings.
          Uses all slaves in the active aggregator according to the 802.3ad
          specification.

        - ``balance-tlb``: Adaptive transmit load balancing: channel bonding
          that does not require any special switch support.

        - ``balance-alb``: Adaptive load balancing: includes balance-tlb plus
          receive load balancing (rlb) for IPV4 traffic, and does not require
          any special switch support. The receive load balancing is achieved by
          ARP negotiation.

        @param (int) "bond_miimon" [required=false] The link monitoring
        freqeuncy in milliseconds.  (Default: 100).

        @param (int) "bond_downdelay" [required=false] Specifies the time, in
        milliseconds, to wait before disabling a slave after a link failure has
        been detected.

        @param (int) "bond_updelay" [required=false] Specifies the time, in
        milliseconds, to wait before enabling a slave after a link recovery has
        been detected.

        @param (string) "bond_lacp_rate" [required=false] Option specifying the
        rate at which to ask the link partner to transmit LACPDU packets in
        802.3ad mode. Available options are ``fast`` or ``slow``. (Default:
        ``slow``).

        @param (string) "bond_xmit_hash_policy" [required=false] The transmit
        hash policy to use for slave selection in balance-xor, 802.3ad, and tlb
        modes. Possible values are: ``layer2``, ``layer2+3``, ``layer3+4``,
        ``encap2+3``, ``encap3+4``. (Default: ``layer2``)

        @param (int) "bond_num_grat_arp" [required=false] The number of peer
        notifications (IPv4 ARP or IPv6 Neighbour Advertisements) to be issued
        after a failover. (Default: 1)

        @param (int) "mtu" [required=false] Maximum transmission unit.

        @param (boolean) "accept_ra" [required=false] Accept router
        advertisements. (IPv6 only)

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new
        bond interface object.
        @success-example "success-json" [exkey=interfaces-create-bond]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.admin
        )
        raise_error_for_invalid_state_on_allocated_operations(
            machine, request.user, "create bond"
        )
        form = BondInterfaceForm(node=machine, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def create_vlan(self, request, system_id):
        """@description-title Create a VLAN interface
        @description Create a VLAN interface on a machine.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (string) "tags" [required=false] Tags for the interface.

        @param (string) "vlan" [required=true] Tagged VLAN the interface is
        connected to.

        @param (int) "parent" [required=true] Parent interface id for this VLAN
        interface.

        @param (int) "mtu" [required=false] Maximum transmission unit.

        @param (boolean) "accept_ra" [required=false] Accept router
        advertisements. (IPv6 only)

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new
        VLAN interface object.
        @success-example "success-json" [exkey=interfaces-placeholder]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.admin
        )
        raise_error_for_invalid_state_on_allocated_operations(
            machine, request.user, "create VLAN"
        )
        # Cast parent to parents to make it easier on the user and to make it
        # work with the form.
        request.data = request.data.copy()
        if "parent" in request.data:
            request.data["parents"] = request.data["parent"]
        form = VLANInterfaceForm(node=machine, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            # Replace parents with parent so it matches the API parameter.
            if "parents" in form.errors:
                form.errors["parent"] = form.errors.pop("parents")
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def create_bridge(self, request, system_id):
        """@description-title Create a bridge interface
        @description Create a bridge interface on a machine.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (string) "name" [required=false] Name of the interface.

        @param (string) "mac_address" [required=false] MAC address of the
        interface.

        @param (string) "tags" [required=false] Tags for the interface.

        @param (string) "vlan" [required=false] VLAN the interface is connected
        to.

        @param (int) "parent" [required=false] Parent interface id for this
        bridge interface.

        @param (string) "bridge_type" [required=false] The type of bridge
        to create. Possible values are: ``standard``, ``ovs``.

        @param (boolean) "bridge_stp" [required=false] Turn spanning tree
        protocol on or off. (Default: False).

        @param (int) "bridge_fd" [required=false] Set bridge forward delay
        to time seconds. (Default: 15).

        @param (int) "mtu" [required=false] Maximum transmission unit.

        @param (boolean) "accept_ra" [required=false] Accept router
        advertisements. (IPv6 only)

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new
        bridge interface object.
        @success-example "success-json" [exkey=interfaces-create-bridge]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Machine matches the given query.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.admin
        )
        raise_error_for_invalid_state_on_allocated_operations(
            machine, request.user, "create bridge"
        )
        # Cast parent to parents to make it easier on the user and to make it
        # work with the form.
        request.data = request.data.copy()
        if "parent" in request.data:
            request.data["parents"] = request.data["parent"]
        if machine.status == NODE_STATUS.ALLOCATED:
            form = AcquiredBridgeInterfaceForm(node=machine, data=request.data)
        else:
            form = BridgeInterfaceForm(node=machine, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            # Replace parents with parent so it matches the API parameter.
            if "parents" in form.errors:
                form.errors["parent"] = form.errors.pop("parents")
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
        return ("interface_handler", (system_id, interface_id))

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
        return sorted(nic.name for nic in interface.parents.all())

    @classmethod
    def children(cls, interface):
        return sorted(
            nic.child.name for nic in interface.children_relationships.all()
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

    @classmethod
    def numa_node(cls, interface):
        numa_node = interface.numa_node
        return numa_node.index if numa_node else None

    def read(self, request, system_id, id):
        """@description-title Read an interface
        @description Read an interface with the given system_id and interface
        id.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (int) "{id}" [required=true] An interface id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new
        requested interface object.
        @success-example "success-json" [exkey=interfaces-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or interface is not
        found.
        @error-example "not-found"
            No Interface matches the given query.
        """
        return Interface.objects.get_interface_or_404(
            system_id, id, request.user, NodePermission.view
        )

    def update(self, request, system_id, id):
        """@description-title Update an interface
        @description Update an interface with the given system_id and interface
        id.

        Note: machines must have a status of Ready or Broken to have access to
        all options. Machines with Deployed status can only have the name
        and/or mac_address updated for an interface. This is intented to allow
        a bad interface to be replaced while the machine remains deployed.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (int) "{id}" [required=true] An interface id.

        @param (string) "name" [required=false] (Physical interfaces) Name of
        the interface.

        @param (string) "mac_address" [required=false] (Physical interfaces)
        MAC address of the interface.

        @param (string) "tags" [required=false] (Physical interfaces) Tags for
        the interface.

        @param (int) "vlan" [required=false] (Physical interfaces) Untagged
        VLAN id the interface is connected to.  If not set then the interface
        is considered disconnected.

        @param (string) "name" [required=false] (Bond interfaces) Name of the
        interface.

        @param (string) "mac_address" [required=false] (Bond interfaces) MAC
        address of the interface.

        @param (string) "tags" [required=false] (Bond interfaces) Tags for the
        interface.

        @param (int) "vlan" [required=false] (Bond interfaces) Untagged VLAN id
        the interface is connected to. If not set then the interface is
        considered disconnected.

        @param (int) "parents" [required=false] (Bond interfaces) Parent
        interface ids that make this bond.

        @param (string) "tags" [required=false] (VLAN interfaces) Tags for the
        interface.

        @param (int) "vlan" [required=false] (VLAN interfaces) Tagged VLAN id
        the interface is connected to.

        @param (int) "parent" [required=false] (VLAN interfaces) Parent
        interface ids for the VLAN interface.

        @param (string) "name" [required=false] (Bridge interfaces) Name of the
        interface.

        @param (string) "mac_address" [required=false] (Bridge interfaces) MAC
        address of the interface.

        @param (string) "tags" [required=false] (Bridge interfaces) Tags for
        the interface.

        @param (int) "vlan" [required=false] (Bridge interfaces) VLAN id the
        interface is connected to.

        @param (int) "parent" [required=false] (Bridge interfaces) Parent
        interface ids for this bridge interface.

        @param (string) "bridge_type" [required=false] (Bridge interfaces) Type
        of bridge to create. Possible values are: ``standard``, ``ovs``.

        @param (boolean) "bridge_stp" [required=false] (Bridge interfaces) Turn
        spanning tree protocol on or off.  (Default: False).

        @param (int) "bridge_fd" [required=false] (Bridge interfaces) Set
        bridge forward delay to time seconds.  (Default: 15).

        @param (int) "bond_miimon" [required=false] (Bonds) The link monitoring
        freqeuncy in milliseconds.  (Default: 100).

        @param (int) "bond_downdelay" [required=false] (Bonds) Specifies the
        time, in milliseconds, to wait before disabling a slave after a link
        failure has been detected.

        @param (int) "bond_updelay" [required=false] (Bonds) Specifies the
        time, in milliseconds, to wait before enabling a slave after a link
        recovery has been detected.

        @param (string) "bond_lacp_rate" [required=false] (Bonds) Option
        specifying the rate in which we'll ask our link partner to transmit
        LACPDU packets in 802.3ad mode.  Available options are ``fast`` or
        ``slow``.  (Default: ``slow``).

        @param (string) "bond_xmit_hash_policy" [required=false] (Bonds) The
        transmit hash policy to use for slave selection in balance-xor,
        802.3ad, and tlb modes.  Possible values are: ``layer2``, ``layer2+3``,
        ``layer3+4``, ``encap2+3``, ``encap3+4``.

        @param (string) "bond_mode" [required=false,formatting=true] (Bonds)
        The operating mode of the bond.  (Default: ``active-backup``).

        Supported bonding modes (bond-mode):

        - ``balance-rr``: Transmit packets in sequential order from the first
          available slave through the last. This mode provides load balancing
          and fault tolerance.

        - ``active-backup``: Only one slave in the bond is active. A different
          slave becomes active if, and only if, the active slave fails. The
          bond's MAC address is externally visible on only one port (network
          adapter) to avoid confusing the switch.

        - ``balance-xor``: Transmit based on the selected transmit hash policy.
          The default policy is a simple [(source MAC address XOR'd with
          destination MAC address XOR packet type ID) modulo slave count].

        - ``broadcast``: Transmits everything on all slave interfaces. This
          mode provides fault tolerance.

        - ``802.3ad``: IEEE 802.3ad Dynamic link aggregation. Creates
          aggregation groups that share the same speed and duplex settings.
          Utilizes all slaves in the active aggregator according to the 802.3ad
          specification.

        - ``balance-tlb``: Adaptive transmit load balancing: channel bonding
          that does not require any special switch support.

        - ``balance-alb``: Adaptive load balancing: includes balance-tlb plus
          receive load balancing (rlb) for IPV4 traffic, and does not require
          any special switch support. The receive load balancing is achieved by
          ARP negotiation.

        @param (string) "mtu" [required=false] Maximum transmission unit.

        @param (string) "accept_ra" [required=false] Accept router
        advertisements. (IPv6 only)

        @param (boolean) "link_connected" [required=false]
        (Physical interfaces) Whether or not the interface is physically
        conntected to an uplink.  (Default: True).

        @param (int) "interface_speed" [required=false] (Physical interfaces)
        The speed of the interface in Mbit/s. (Default: 0).

        @param (int) "link_speed" [required=false] (Physical interfaces)
        The speed of the link in Mbit/s. (Default: 0).

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new
        requested interface object.
        @success-example "success-json" [exkey=interfaces-update] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or interface is not
        found.
        @error-example "not-found"
            No Interface matches the given query.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id,
            id,
            request.user,
            NodePermission.admin,
            NodePermission.edit,
        )
        node = interface.get_node()
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                node,
                request.user,
                "update interface",
                extra_states=[NODE_STATUS.DEPLOYED],
            )
        if node.is_controller:
            if interface.type == INTERFACE_TYPE.VLAN:
                raise MAASAPIForbidden(
                    "Cannot modify VLAN interface on controller."
                )
            interface_form = ControllerInterfaceForm
        elif node.status == NODE_STATUS.DEPLOYED:
            interface_form = DeployedInterfaceForm
        else:
            interface_form = InterfaceForm.get_interface_form(interface.type)
        # For VLAN interface we cast parents to parent. As a VLAN can only
        # have one parent.
        if interface.type == INTERFACE_TYPE.VLAN:
            request.data = request.data.copy()
            if "parent" in request.data:
                request.data["parents"] = request.data["parent"]
        form = interface_form(instance=interface, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            # Replace parents with parent so it matches the API parameter, if
            # the interface being editted was a VLAN interface.
            if (
                interface.type == INTERFACE_TYPE.VLAN
                and "parents" in form.errors
            ):
                form.errors["parent"] = form.errors.pop("parents")
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, system_id, id):
        """@description-title Delete an interface
        @description Delete an interface with the given system_id and interface
        id.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (int) "{id}" [required=true] An interface id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or interface is not
        found.
        @error-example "not-found"
            No Interface matches the given query.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id,
            id,
            request.user,
            NodePermission.admin,
            NodePermission.edit,
        )
        node = interface.get_node()
        raise_error_if_controller(node, "delete interface")
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                interface.node_config.node, request.user, "delete interface"
            )
        interface.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def link_subnet(self, request, system_id, id):
        """@description-title Link interface to a subnet
        @description Link an interface with the given system_id and interface
        id to a subnet.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (int) "{id}" [required=true] An interface id.

        @param (string) "mode" [required=true,formatting=true] ``AUTO``,
        ``DHCP``, ``STATIC`` or ``LINK_UP`` connection to subnet.

        Mode definitions:

        - ``AUTO``: Assign this interface a static IP address from the provided
          subnet. The subnet must be a managed subnet. The IP address will not
          be assigned until the node goes to be deployed.

        - ``DHCP``: Bring this interface up with DHCP on the given subnet. Only
          one subnet can be set to ``DHCP``. If the subnet is managed this
          interface will pull from the dynamic IP range.

        - ``STATIC``: Bring this interface up with a static IP address on the
          given subnet. Any number of static links can exist on an interface.

        - ``LINK_UP``: Bring this interface up only on the given subnet. No IP
          address will be assigned to this interface. The interface cannot have
          any current ``AUTO``, ``DHCP`` or ``STATIC`` links.

        @param (int) "subnet" [required=true] Subnet id linked to interface.

        @param (string) "ip_address" [required=false] IP address for the
        interface in subnet. Only used when mode is ``STATIC``. If not provided
        an IP address from subnet will be auto selected.

        @param (boolean) "force" [required=false] If True, allows ``LINK_UP``
        to be set on the interface even if other links already exist. Also
        allows the selection of any VLAN, even a VLAN MAAS does not believe the
        interface to currently be on. Using this option will cause all other
        links on the interface to be deleted. (Defaults to False.)

        @param (string) "default_gateway" [required=false] True sets the
        gateway IP address for the subnet as the default gateway for the node
        this interface belongs to. Option can only be used with the ``AUTO``
        and ``STATIC`` modes.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new update
        interface object.
        @success-example "success-json" [exkey=interfaces-link-subnet]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or interface is not
        found.
        @error-example "not-found"
            No Interface matches the given query.
        """
        force = get_optional_param(
            request.POST, "force", default=False, validator=StringBool
        )
        interface = Interface.objects.get_interface_or_404(
            system_id,
            id,
            request.user,
            NodePermission.admin,
            NodePermission.edit,
        )
        node = interface.get_node()
        raise_error_if_controller(node, "link subnet")
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "link subnet"
            )
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
            instance=interface,
            data=request.data,
            allowed_modes=allowed_modes,
            force=force,
        )
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def disconnect(self, request, system_id, id):
        """@description-title Disconnect an interface
        @description Disconnect an interface with the given system_id and
        interface id.

        Deletes any linked subnets and IP addresses, and disconnects the
        interface from any associated VLAN.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        interface object.
        @success-example "success-json" [exkey=interfaces-disconnect]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or interface is not
        found.
        @error-example "not-found"
            No Interface matches the given query.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id,
            id,
            request.user,
            NodePermission.admin,
            NodePermission.edit,
        )
        node = interface.get_node()
        raise_error_if_controller(node, "disconnect")
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "disconnect"
            )
        interface.ip_addresses.all().delete()
        interface.vlan = None
        interface.save()
        return interface

    @operation(idempotent=False)
    def unlink_subnet(self, request, system_id, id):
        """@description-title Unlink interface from subnet
        @description Unlink an interface with the given system_id and interface
        id from a subnet.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (int) "{id}" [required=true] An interface id.

        @param (int) "id" [required=false] ID of the subnet link on the
        interface to remove.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        interface object.
        @success-example "success-json" [exkey=interfaces-unlink-subnet]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or interface is not
        found.
        @error-example "not-found"
            No Interface matches the given query.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id,
            id,
            request.user,
            NodePermission.admin,
            NodePermission.edit,
        )
        node = interface.get_node()
        raise_error_if_controller(node, "link subnet")
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "unlink subnet"
            )
        form = InterfaceUnlinkForm(instance=interface, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def set_default_gateway(self, request, system_id, id):
        """@description-title Set the default gateway on a machine
        @description Set the given interface id on the given system_id as the
        default gateway.

        If this interface has more than one subnet with a gateway IP in the
        same IP address family then specifying the ID of the link on
        this interface is required.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (int) "{id}" [required=true] An interface id.

        @param (int) "link_id" [required=false] ID of the link on this
        interface to select the default gateway IP address from.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        interface object.
        @success-example "success-json" [exkey=interfaces-set-def-gateway]
        placeholder text

        @error (http-status-code) "400" 400
        @error (content) "400" If the interface has no ``AUTO`` or ``STATIC``
        links.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or interface is not
        found.
        @error-example "not-found"
            No Interface matches the given query.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id,
            id,
            request.user,
            NodePermission.admin,
            NodePermission.edit,
        )
        node = interface.get_node()
        raise_error_if_controller(node, "link subnet")
        if node.node_type == NODE_TYPE.MACHINE:
            # This node needs to be in the correct state to modify
            # the interface.
            raise_error_for_invalid_state_on_allocated_operations(
                node, request.user, "set default gateway"
            )
        form = InterfaceSetDefaultGatwayForm(
            instance=interface, data=request.data
        )
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def add_tag(self, request, system_id, id):
        """@description-title Add a tag to an interface
        @description Add a tag to an interface with the given system_id and
        interface id.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (int) "{id}" [required=true] An interface id.

        @param (string) "tag" [required=false] The tag to add.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        interface object.
        @success-example "success-json" [exkey=interfaces-add-tag] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "403" If the user does not have the permission to add
        a tag.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or interface is not
        found.
        @error-example "not-found"
            No Interface matches the given query.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id,
            id,
            request.user,
            NodePermission.admin,
            NodePermission.edit,
        )
        interface.add_tag(get_mandatory_param(request.POST, "tag"))
        interface.save()
        return interface

    @operation(idempotent=False)
    def remove_tag(self, request, system_id, id):
        """@description-title Remove a tag from an interface
        @description Remove a tag from an interface with the given system_id
        and interface id.

        @param (string) "{system_id}" [required=true] A system_id.

        @param (int) "{id}" [required=true] An interface id.

        @param (string) "tag" [required=false] The tag to remove.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        interface object.
        @success-example "success-json" [exkey=interfaces-remove-tag]
        placeholder text

        @error (http-status-code) "403" 403
        @error (content) "403" If the user does not have the permission to add
        a tag.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or interface is not
        found.
        @error-example "not-found"
            No Interface matches the given query.
        """
        interface = Interface.objects.get_interface_or_404(
            system_id,
            id,
            request.user,
            NodePermission.admin,
            NodePermission.edit,
        )
        interface.remove_tag(get_mandatory_param(request.POST, "tag"))
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
