# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for NodeGroupInterface."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'NodeGroupInterface',
    ]


from collections import defaultdict
from textwrap import dedent

from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
)
from maasserver import DefaultMeta
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    NODEGROUPINTERFACE_MANAGEMENT_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT,
)
from maasserver.fields import (
    MAASIPAddressField,
    VerboseRegexValidator,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.timestampedmodel import TimestampedModel
from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
)
from netaddr.core import AddrFormatError
from provisioningserver.network import REVEAL_IPv6
from provisioningserver.utils.network import (
    intersect_iprange,
    make_network,
)

# UI explanation for subnet_mask field.
SUBNET_MASK_HELP = "e.g. 255.255.255.0"
if REVEAL_IPv6:
    SUBNET_MASK_HELP += " (defaults to 64-bit netmask for IPv6)."


# UI explanation for broadcast_ip field.
BROADCAST_IP_HELP = "e.g. 192.168.1.255"
if REVEAL_IPv6:
    BROADCAST_IP_HELP += " (for IPv4 networks only)."


class NodeGroupInterfaceManager(Manager):
    """Manager for NodeGroupInterface objects"""

    find_by_network_for_static_allocation_query = dedent("""\
    SELECT ngi.*
      FROM maasserver_nodegroup AS ng,
           maasserver_nodegroupinterface AS ngi
     WHERE ng.status = %s
       AND ngi.nodegroup_id = ng.id
       AND ngi.static_ip_range_low IS NOT NULL
       AND ngi.static_ip_range_high IS NOT NULL
       AND (ngi.ip & ngi.subnet_mask) = (INET %s)
     ORDER BY ng.id, ngi.id
    """)

    def find_by_network_for_static_allocation(self, network):
        """Find all cluster interfaces with the given network.

        Furthermore, each interface must also have a static range defined.
        """
        assert isinstance(network, IPNetwork), (
            "%r is not an IPNetwork" % (network,))
        return self.raw(
            self.find_by_network_for_static_allocation_query,
            [NODEGROUP_STATUS.ENABLED, network.network.format()])

    def get_by_network_for_static_allocation(self, network):
        """Return the first cluster interface with the given network.

        Furthermore, the interface must also have a static range defined.
        """
        assert isinstance(network, IPNetwork), (
            "%r is not an IPNetwork" % (network,))
        interfaces = self.raw(
            self.find_by_network_for_static_allocation_query + " LIMIT 1",
            [NODEGROUP_STATUS.ENABLED, network.network.format()])
        for interface in interfaces:
            return interface  # This is stable because the query is ordered.
        else:
            return None

    find_by_address_query = dedent("""\
    SELECT ngi.*
      FROM maasserver_nodegroup AS ng,
           maasserver_nodegroupinterface AS ngi
     WHERE ng.status = %s
       AND ngi.nodegroup_id = ng.id
       AND (ngi.ip & ngi.subnet_mask) = (INET %s & ngi.subnet_mask)
     ORDER BY ng.id, ngi.id
    """)

    def find_by_address(self, address):
        """Find all cluster interfaces for a given address."""
        assert isinstance(address, IPAddress), (
            "%r is not an IPAddress" % (address,))
        return self.raw(
            self.find_by_address_query,
            [NODEGROUP_STATUS.ENABLED, address.format()])

    def get_by_address(self, address):
        """Return the first interface that could contain `address`."""
        assert isinstance(address, IPAddress), (
            "%r is not an IPAddress" % (address,))
        interfaces = self.raw(
            self.find_by_address_query + " LIMIT 1",
            [NODEGROUP_STATUS.ENABLED, address.format()])
        for interface in interfaces:
            return interface  # This is stable because the query is ordered.
        else:
            return None

    find_by_address_for_static_allocation_query = dedent("""\
    SELECT ngi.*
      FROM maasserver_nodegroup AS ng,
           maasserver_nodegroupinterface AS ngi
     WHERE ng.status = %s
       AND ngi.nodegroup_id = ng.id
       AND ngi.static_ip_range_low IS NOT NULL
       AND ngi.static_ip_range_high IS NOT NULL
       AND (ngi.ip & ngi.subnet_mask) = (INET %s & ngi.subnet_mask)
     ORDER BY ng.id, ngi.id
    """)

    def find_by_address_for_static_allocation(self, address):
        """Find all cluster interfaces for the given address.

        Furthermore, each interface must also have a static range defined.
        """
        assert isinstance(address, IPAddress), (
            "%r is not an IPAddress" % (address,))
        return self.raw(
            self.find_by_address_for_static_allocation_query,
            [NODEGROUP_STATUS.ENABLED, address.format()])

    def get_by_address_for_static_allocation(self, address):
        """Return the first interface that could contain `address`.

        Furthermore, the interface must also have a static range defined.
        """
        assert isinstance(address, IPAddress), (
            "%r is not an IPAddress" % (address,))
        interfaces = self.raw(
            self.find_by_address_for_static_allocation_query + " LIMIT 1",
            [NODEGROUP_STATUS.ENABLED, address.format()])
        for interface in interfaces:
            return interface  # This is stable because the query is ordered.
        else:
            return None


class NodeGroupInterface(CleanSave, TimestampedModel):
    """Cluster interface.

    Represents a network to which a given cluster controller is connected.
    These interfaces are discovered automatically, but an admin can also
    add/edit/remove them.

    This class duplicates some of :class:`Network`, and adds settings for
    managing DHCP.  Some day we hope to delegate the duplicated fields, and
    have auto-discovery populate the :class:`Network` model along the way.
    """

    class Meta(DefaultMeta):
        # The API identifies a NodeGroupInterface by cluster and name.
        unique_together = ('nodegroup', 'name')

    objects = NodeGroupInterfaceManager()

    # Static IP of the network interface.
    ip = MAASIPAddressField(
        null=False, editable=True,
        help_text="Static IP Address of the interface",
        verbose_name="IP")

    # The `NodeGroup` this interface belongs to.
    nodegroup = ForeignKey(
        'maasserver.NodeGroup', editable=True, null=False, blank=False)

    # Name for this interface.  It must be unique within the cluster.
    # The code ensures that this is never an empty string, but we do allow
    # an empty string on the form.  The field defaults to a unique name based
    # on the network interface name.
    name = CharField(
        blank=True, null=False, editable=True, max_length=255, default='',
        validators=[VerboseRegexValidator('^[\w:.-]+$')],
        help_text=(
            "Identifying name for this cluster interface.  "
            "Must be unique within the cluster, and consist only of letters, "
            "digits, dashes, and colons."))

    management = IntegerField(
        choices=NODEGROUPINTERFACE_MANAGEMENT_CHOICES, editable=True,
        default=NODEGROUPINTERFACE_MANAGEMENT.DEFAULT)

    # DHCP server settings.
    interface = CharField(
        blank=True, editable=True, max_length=255, default='',
        help_text="Network interface (e.g. 'eth1').")
    subnet_mask = MAASIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None,
        help_text=SUBNET_MASK_HELP)
    broadcast_ip = MAASIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None,
        verbose_name="Broadcast IP",
        help_text=BROADCAST_IP_HELP)
    router_ip = MAASIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None,
        verbose_name="Router IP",
        help_text="IP of this network's router given to DHCP clients")
    ip_range_low = MAASIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None,
        verbose_name="DHCP dynamic IP range low value",
        help_text="Lowest IP number of the range for dynamic IPs, used for "
                  "enlistment, commissioning and unknown devices.")
    ip_range_high = MAASIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None,
        verbose_name="DHCP dynamic IP range high value",
        help_text="Highest IP number of the range for dynamic IPs, used for "
                  "enlistment, commissioning and unknown devices.")
    static_ip_range_low = MAASIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None,
        verbose_name="Static IP range low value",
        help_text="Lowest IP number of the range for IPs given to allocated "
                  "nodes, must be in same network as dynamic range.")
    static_ip_range_high = MAASIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None,
        verbose_name="Static IP range high value",
        help_text="Highest IP number of the range for IPs given to allocated "
                  "nodes, must be in same network as dynamic range.")

    # Foreign DHCP server address, if any, that was detected on this
    # interface.
    foreign_dhcp_ip = MAASIPAddressField(
        null=True, default=None, editable=True, blank=True, unique=False)

    @property
    def network(self):
        """Return the network defined by the interface's address and netmask.

        :return: :class:`IPNetwork`, or `None` if the netmask is unset.
        :raise AddrFormatError: If the combination of interface address and
            subnet mask is malformed.
        """
        ip = self.ip
        netmask = self.subnet_mask
        # Nullness check for GenericIPAddress fields is deliberately kept
        # vague: MAASIPAddressField seems to represent nulls as empty
        # strings.
        if netmask:
            return make_network(ip, netmask).cidr
        else:
            return None

    @property
    def is_managed(self):
        """Return true if this interface is managed by MAAS."""
        return self.management != NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED

    def check_for_network_interface_clashes(self, exclude):
        """Validate uniqueness rules for network interfaces.

        This enforces the rules that there can be only one IPv4 cluster
        interface on a given network interface on the cluster controller, and
        that there can be only one IPv6 cluster interface with a static range
        on a given network interface on the cluster controller.  Aliases and
        VLANs count as separate network interfaces.

        The IPv4 rule is inherent: a network interface (as seen in userspace)
        can only be on one IPv4 subnet.  The IPv6 rule is needed because our
        current way of configuring IPv6 addresses on nodes, in `/etc/network`,
        does not support multiple addresses.  So a network interface on a node
        can only be on one IPv6 subnet.  Since the node's network interface is
        connected to the same network segment as the cluster controller's, that
        means that the cluster controller can only manage static IP addresses
        on one IPv6 subnet per network interface.
        """
        if 'ip' in exclude or 'nodegroup' in exclude or 'interface' in exclude:
            return
        ip_version = IPAddress(self.ip).version
        similar_interfaces = self.nodegroup.nodegroupinterface_set.filter(
            interface=self.interface)
        if self.id is not None:
            similar_interfaces = similar_interfaces.exclude(id=self.id)
        potential_clashes = [
            itf
            for itf in similar_interfaces
            if IPAddress(itf.ip).version == ip_version
            ]
        if ip_version == 4:
            if potential_clashes != []:
                raise ValidationError(
                    "Another cluster interface already connects "
                    "network interface %s to an IPv4 network."
                    % self.interface)
        elif self.static_ip_range_low and self.static_ip_range_high:
            # Nullness checks for these IP addresses are deliberately vague
            # because Django may represent them as either empty strings or
            # None.
            clashes = [
                itf
                for itf in potential_clashes
                if itf.static_ip_range_low and itf.static_ip_range_high
                ]
            if clashes != []:
                raise ValidationError(
                    "Another cluster interface with a static address range "
                    "already connects network interface %s to an IPv6 network."
                    % self.interface)

    def validate_unique(self, exclude=None):
        """Validate against conflicting `NodeGroupInterface` objects."""
        super(NodeGroupInterface, self).validate_unique(exclude=exclude)
        if exclude is None:
            exclude = []
        self.check_for_network_interface_clashes(exclude)

    def get_dynamic_ip_range(self):
        if self.ip_range_low and self.ip_range_high:
            return IPRange(
                self.ip_range_low,
                self.ip_range_high)
        else:
            return None

    def get_static_ip_range(self):
        if self.static_ip_range_low and self.static_ip_range_high:
            return IPRange(
                self.static_ip_range_low,
                self.static_ip_range_high)
        else:
            return None

    def display_management(self):
        """Return management status text as displayed to the user."""
        return NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT[self.management]

    def __repr__(self):
        return "<NodeGroupInterface %s,%s>" % (
            self.nodegroup.uuid, self.name)

    def clean_network_valid(self):
        """Validate the network.

        This validates that the network defined by `ip` and `subnet_mask` is
        valid.
        """
        try:
            self.network
        except AddrFormatError as e:
            # The interface's address is validated separately.  If the
            # combination with the netmask is invalid, either there's already
            # going to be a specific validation error for the IP address, or
            # the failure is due to an invalid netmask.
            raise ValidationError({'subnet_mask': [e.message]})

    def clean_network_config_if_managed(self):
        # If management is not 'UNMANAGED', all the network information
        # should be provided.
        if self.is_managed:
            mandatory_fields = [
                'interface',
                'subnet_mask',
                'ip_range_low',
                'ip_range_high',
            ]
            errors = {}
            for field in mandatory_fields:
                if not getattr(self, field):
                    errors[field] = [
                        "That field cannot be empty (unless that interface is "
                        "'unmanaged')"]
            if len(errors) != 0:
                raise ValidationError(errors)

    def clean_ips_in_network(self):
        """Ensure that the network settings are all congruent.

        Specifically, it ensures that the router address, the DHCP address
        range, and the broadcast address if given, all fall within the network
        defined by the interface's IP address and the subnet mask.

        If no broadcast address is given, the network's default broadcast
        address will be used.
        """
        network = self.network
        if network is None:
            return
        network_settings = (
            ("broadcast_ip", self.broadcast_ip),
            ("router_ip", self.router_ip),
            ("ip_range_low", self.ip_range_low),
            ("ip_range_high", self.ip_range_high),
            ("static_ip_range_low", self.static_ip_range_low),
            ("static_ip_range_high", self.static_ip_range_high),
            )
        network_errors = defaultdict(list)
        for field, address in network_settings:
            if address and IPAddress(address) not in network:
                network_errors[field].append(
                    "%s not in the %s network" % (address, network))
        if len(network_errors) != 0:
            raise ValidationError(network_errors)

        # Deliberately vague nullness check.  A null IP address seems to be
        # None in some situations, or an empty string in others.
        if not self.broadcast_ip:
            # No broadcast address given.  Set the default.  Set it in string
            # form; validation breaks if we pass an IPAddress.
            self.broadcast_ip = unicode(network.broadcast)

    def manages_static_range(self):
        """Is this a managed interface with a static IP range configured?"""
        # Deliberately vague implicit conversion to bool: a blank IP address
        # can show up internally as either None or an empty string.
        return (
            self.is_managed and
            self.static_ip_range_low and
            self.static_ip_range_high
            )

    def clean_ip_range_bounds(self):
        """Ensure that the static and dynamic ranges have sane bounds."""
        if not self.manages_static_range():
            # Exit early with nothing to do.
            return

        errors = {}
        ip_range_low = IPAddress(self.ip_range_low)
        ip_range_high = IPAddress(self.ip_range_high)
        static_ip_range_low = IPAddress(self.static_ip_range_low)
        static_ip_range_high = IPAddress(self.static_ip_range_high)

        message_base = (
            "Lower bound %s is higher than upper bound %s")
        try:
            IPRange(static_ip_range_low, static_ip_range_high)
        except AddrFormatError:
            message = (
                message_base % (
                    self.static_ip_range_low, self.static_ip_range_high))
            errors['static_ip_range_low'] = [message]
            errors['static_ip_range_high'] = [message]
        try:
            IPRange(ip_range_low, ip_range_high)
        except AddrFormatError:
            message = (
                message_base % (self.ip_range_low, self.ip_range_high))
            errors['ip_range_low'] = [message]
            errors['ip_range_high'] = [message]

        if errors:
            raise ValidationError(errors)

    def clean_ip_ranges(self):
        """Ensure that the static and dynamic ranges don't overlap."""
        if not self.manages_static_range():
            # Nothing to do; bail out.
            return

        errors = {}
        ip_range_low = IPAddress(self.ip_range_low)
        ip_range_high = IPAddress(self.ip_range_high)
        static_ip_range_low = IPAddress(self.static_ip_range_low)
        static_ip_range_high = IPAddress(self.static_ip_range_high)

        static_range = IPRange(
            static_ip_range_low, static_ip_range_high)
        dynamic_range = IPRange(
            ip_range_low, ip_range_high)

        # This is a bit unattractive, but we can't use IPSet for
        # large networks - it's far too slow. What we actually care
        # about is whether the lows and highs of the static range
        # fall within the dynamic range and vice-versa, which
        # IPRange gives us.
        networks_overlap = (
            static_ip_range_low in dynamic_range or
            static_ip_range_high in dynamic_range or
            ip_range_low in static_range or
            ip_range_high in static_range
        )
        if networks_overlap:
            message = "Static and dynamic IP ranges may not overlap."
            errors = {
                'ip_range_low': [message],
                'ip_range_high': [message],
                'static_ip_range_low': [message],
                'static_ip_range_high': [message],
                }
            raise ValidationError(errors)

    def clean_overlapping_networks(self):
        """Ensure that this interface's network doesn't overlap those of
        other interfaces on this cluster.
        """
        try:
            nodegroup = self.nodegroup
        except NodeGroup.DoesNotExist:
            # We're likely being called on nodegroup creation, so
            # there's no nodegroup linked to this interface yet. Since
            # we don't have a nodegroup we can't check whether any other
            # interfaces on this nodegroup have overlapping network
            # settings.
            return

        if not self.is_managed:
            return

        network = self.network
        current_cluster_interfaces = (
            NodeGroupInterface.objects.filter(nodegroup=nodegroup)
            .exclude(management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
            .exclude(id=self.id))
        network_overlaps_other_interfaces = any(
            intersect_iprange(network, interface.network) is not None
            for interface in current_cluster_interfaces
            )
        if network_overlaps_other_interfaces:
            message = (
                "This interface's network must not overlap with other "
                "networks on this cluster.")
            errors = {
                'ip': [message],
                'subnet_mask': [message],
            }
            raise ValidationError(errors)

    def clean_fields(self, *args, **kwargs):
        super(NodeGroupInterface, self).clean_fields(*args, **kwargs)
        self.clean_network_valid()
        self.clean_ips_in_network()
        self.clean_network_config_if_managed()
        self.clean_ip_range_bounds()
        self.clean_ip_ranges()
        self.clean_overlapping_networks()
