# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MACAddress model and friends."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'MACAddress',
    ]


import re

from django.db.models import (
    ForeignKey,
    ManyToManyField,
    )
from maasserver import DefaultMeta
from maasserver.enum import IPADDRESS_TYPE
from maasserver.exceptions import StaticIPAddressTypeClash
from maasserver.fields import (
    MAC,
    MACAddressField,
    )
from maasserver.models.cleansave import CleanSave
from maasserver.models.managers import BulkManager
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.models.timestampedmodel import TimestampedModel


mac_re = re.compile(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$')


class MACAddress(CleanSave, TimestampedModel):
    """A `MACAddress` represents a `MAC address`_ attached to a :class:`Node`.

    :ivar mac_address: The MAC address.
    :ivar node: The :class:`Node` related to this `MACAddress`.
    :ivar networks: The networks related to this `MACAddress`.

    .. _MAC address: http://en.wikipedia.org/wiki/MAC_address
    """
    mac_address = MACAddressField(unique=True)
    node = ForeignKey('Node', editable=False)

    networks = ManyToManyField('maasserver.Network', blank=True)

    ip_addresses = ManyToManyField(
        'maasserver.StaticIPAddress',
        through='maasserver.MACStaticIPAddressLink', blank=True)

    # Will be set only once we know on which cluster interface this MAC
    # is connected, normally after the first DHCPLease appears.
    cluster_interface = ForeignKey(
        'NodeGroupInterface', editable=False, blank=True, null=True,
        default=None)

    # future columns: tags, nic_name, metadata, bonding info

    objects = BulkManager()

    class Meta(DefaultMeta):
        verbose_name = "MAC address"
        verbose_name_plural = "MAC addresses"
        ordering = ('created', )

    def __unicode__(self):
        address = self.mac_address
        if isinstance(address, MAC):
            address = address.get_raw()
        if isinstance(address, bytes):
            address = address.decode('utf-8')
        return address

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ('mac_address',):
                return "This MAC address is already registered."
        return super(
            MACAddress, self).unique_error_message(model_class, unique_check)

    def get_networks(self):
        """Return networks to which this MAC is connected, sorted by name."""
        return self.networks.all().order_by('name')

    def get_cluster_interfaces(self):
        """Return all cluster interfaces to which this MAC connects.

        This is at least its `cluster_interface`, if it is set.  But if so,
        there may also be an IPv6 cluster interface attached to the same
        network interface.
        """
        # XXX jtv 2014-08-18 bug=1358130: cluster_interface should probably be
        # an m:n relationship.  Andres came up with a simpler scheme for the
        # short term: "for IPv6, use whatever network interface on the cluster
        # also manages the node's IPv4 address."
        if self.cluster_interface is None:
            # No known cluster interface.  Nothing we can do.
            return []
        else:
            return NodeGroupInterface.objects.filter(
                nodegroup=self.cluster_interface.nodegroup,
                interface=self.cluster_interface.interface)

    def claim_static_ips(self, alloc_type=IPADDRESS_TYPE.AUTO,
                         requested_address=None):
        """Assign static IP addresses to this MAC.

        Allocates one address per managed cluster interface connected to this
        MAC.  Typically this will be either just one IPv4 address, or an IPv4
        address and an IPv6 address.

        It is the caller's responsibility to create a celery Task that will
        write the dhcp host.  It is not done here because celery doesn't
        guarantee job ordering, and if the host entry is written after
        the host boots it is too late.

        :param alloc_type: See :class:`StaticIPAddress`.alloc_type.
            This parameter musn't be IPADDRESS_TYPE.USER_RESERVED.
        :param requested_address: Optional IP address to claim.  Must be in
            the range defined on a cluster interface to which this MACAddress
            is related.  If given, no allocations will be made on any other
            cluster interfaces the MAC may be connected to.
        :return: A list of :class:`StaticIPAddress`.  Returns empty if
            the cluster_interface is not yet known, or the
            static_ip_range_low/high values values are not set on the
            cluster_interface.  If an IP address was already allocated, the
            function will return it rather than allocate a new one.
        :raises: StaticIPAddressExhaustion if there are not enough IPs left.
        :raises: StaticIPAddressTypeClash if an IP already exists with a
            different type.
        :raises: StaticIPAddressOutOfRange if the requested_address is not in
            the cluster interface's defined range.
        :raises: StaticIPAddressUnavailable if the requested_address is already
            allocated.
        """
        # Avoid circular import.
        from maasserver.models.staticipaddress import StaticIPAddress

        # Check for clashing type.  This depends on database
        # serialisation to avoid being a race.
        clash = StaticIPAddress.objects.filter(macaddress=self).exclude(
            alloc_type=alloc_type)
        if clash.exists():
            raise StaticIPAddressTypeClash(
                "%s already has an IP with a different type" % self)

        # Check to see if an IP with the same type already exists.
        try:
            return [StaticIPAddress.objects.get(
                macaddress=self, alloc_type=alloc_type)]
        except StaticIPAddress.DoesNotExist:
            pass

        if self.cluster_interface is None:
            # We need to know this to allocate an IP, so return nothing.
            return []

        low = self.cluster_interface.static_ip_range_low
        high = self.cluster_interface.static_ip_range_high
        if not low or not high:
            # low/high can be None or blank if not defined yet.
            return []

        # Avoid circular imports.
        from maasserver.models import (
            MACStaticIPAddressLink,
            StaticIPAddress,
            )
        sip = StaticIPAddress.objects.allocate_new(
            low, high, alloc_type, requested_address=requested_address)
        MACStaticIPAddressLink(mac_address=self, ip_address=sip).save()
        return [sip]
