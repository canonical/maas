# Copyright 2012 Canonical Ltd.  This software is licensed under the
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

from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    ForeignKey,
    GenericIPAddressField,
    IntegerField,
    )
from maasserver import DefaultMeta
from maasserver.enum import (
    NODEGROUPINTERFACE_MANAGEMENT,
    NODEGROUPINTERFACE_MANAGEMENT_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT,
    )
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from netaddr import (
    IPAddress,
    IPNetwork,
    )
from netaddr.core import AddrFormatError

# The minimum number of leading bits of the routing prefix for a
# network.  A smaller number will be rejected as it creates a huge
# address space that is currently not well supported by the DNS
# machinery.
# For instance, if MINIMUM_NETMASK_BITS is 9, a /8 will be rejected.
MINIMUM_NETMASK_BITS = 16


class NodeGroupInterface(CleanSave, TimestampedModel):

    class Meta(DefaultMeta):
        unique_together = ('nodegroup', 'interface')

    # Static IP of the interface.
    ip = GenericIPAddressField(
        null=False, editable=True,
        help_text="Static IP Address of the interface")

    # The `NodeGroup` this interface belongs to.
    nodegroup = ForeignKey(
        'maasserver.NodeGroup', editable=True, null=False, blank=False)

    management = IntegerField(
        choices=NODEGROUPINTERFACE_MANAGEMENT_CHOICES, editable=True,
        default=NODEGROUPINTERFACE_MANAGEMENT.DEFAULT)

    # DHCP server settings.
    interface = CharField(
        blank=True, editable=True, max_length=255, default='',
        help_text="Name of this interface (e.g. 'em1').")
    subnet_mask = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    broadcast_ip = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    router_ip = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    ip_range_low = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    ip_range_high = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)

    # Foreign DHCP server address, if any, that was detected on this
    # interface.
    foreign_dhcp_ip = GenericIPAddressField(
        null=True, default=None, editable=True, blank=True, unique=False)

    @property
    def network(self):
        """Return the network defined by the broadcast address and net mask.

        If either the broadcast address or the subnet mask is unset, returns
        None.

        :return: :class:`IPNetwork`
        """
        if self.broadcast_ip and self.subnet_mask:
            return IPNetwork("%s/%s" % (self.broadcast_ip, self.subnet_mask))
        return None

    def display_management(self):
        """Return management status text as displayed to the user."""
        return NODEGROUPINTERFACE_MANAGEMENT_CHOICES_DICT[self.management]

    def __repr__(self):
        return "<NodeGroupInterface %s,%s>" % (
            self.nodegroup.uuid, self.interface)

    def clean_network_valid(self):
        """Validate the network.

        This validates that the network defined by broadcast_ip and
        subnet_mask is valid.
        """
        try:
            self.network
        except AddrFormatError, e:
            # Technically, this should be a global error but it's
            # more user-friendly to precisely point out where the error
            # comes from.
            raise ValidationError(
                {
                    'broadcast_ip': [e.message],
                    'subnet_mask': [e.message],
                })

    def clean_network_not_too_big(self):
        # If management is not 'UNMANAGED', refuse huge networks.
        if self.management != NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED:
            network = self.network
            if network is not None:
                if network.prefixlen < MINIMUM_NETMASK_BITS:
                    message = (
                        "Cannot create an address space bigger than "
                        "a /%d network.  This network is a /%d network." % (
                            MINIMUM_NETMASK_BITS, network.prefixlen))
                    raise ValidationError({
                        'broadcast_ip': [message],
                        'subnet_mask': [message],
                    })

    def clean_management(self):
        # XXX: rvb 2012-09-18 bug=1052339: Only one "managed" interface
        # is supported per NodeGroup.
        check_other_interfaces = (
            self.management != NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED and
            self.nodegroup_id is not None)
        if check_other_interfaces:
            other_interfaces = self.nodegroup.nodegroupinterface_set.all()
            # Exclude context if it's already in the database.
            if self.id is not None:
                other_interfaces = (
                    other_interfaces.exclude(id=self.id))
            # Narrow down to the those that are managed.
            other_managed_interfaces = other_interfaces.exclude(
                management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
            if other_managed_interfaces.exists():
                raise ValidationError(
                    {'management': [
                        "Another managed interface already exists for this "
                        "cluster."]})

    def clean_network_config_if_managed(self):
        # If management is not 'UNMANAGED', all the network information
        # should be provided.
        if self.management != NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED:
            mandatory_fields = [
                'interface',
                'broadcast_ip',
                'subnet_mask',
                'router_ip',
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

        Specifically, it ensures that the interface address, router address,
        and the address range, all fall within the network defined by the
        broadcast address and subnet mask.
        """
        network = self.network
        if network is None:
            return
        network_settings = (
            ("ip", self.ip),
            ("router_ip", self.router_ip),
            ("ip_range_low", self.ip_range_low),
            ("ip_range_high", self.ip_range_high),
            )
        network_errors = defaultdict(list)
        for field, address in network_settings:
            if address and IPAddress(address) not in network:
                network_errors[field].append(
                    "%s not in the %s network" % (address, network))
        if len(network_errors) != 0:
            raise ValidationError(network_errors)

    def clean_fields(self, *args, **kwargs):
        super(NodeGroupInterface, self).clean_fields(*args, **kwargs)
        self.clean_network_valid()
        self.clean_network_not_too_big()
        self.clean_ips_in_network()
        self.clean_management()
        self.clean_network_config_if_managed()
