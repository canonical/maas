# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for StaticIPAddress.

Contains all the in-use static IP addresses that are allocated by MAAS.
Generally speaking, these are written out to the DHCP server as "host"
blocks which will tie MACs into a specific IP.  The IPs are separate
from the dynamic range that the DHCP server itself allocates to unknown
clients.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'StaticIPAddress',
    ]


from django.contrib.auth.models import User
from django.db import connection
from django.db.models import (
    ForeignKey,
    IntegerField,
    Manager,
    )
from maasserver import DefaultMeta
from maasserver.enum import IPADDRESS_TYPE
from maasserver.exceptions import (
    StaticIPAddressExhaustion,
    StaticIPAddressOutOfRange,
    StaticIPAddressUnavailable,
    )
from maasserver.fields import MAASIPAddressField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils import strip_domain
from netaddr import (
    IPAddress,
    IPRange,
    )


class StaticIPAddressManager(Manager):
    """A utility to manage collections of IPAddresses."""

    def allocate_new(self, range_low, range_high,
                     alloc_type=IPADDRESS_TYPE.AUTO, user=None,
                     requested_address=None):
        """Return a new StaticIPAddress.

        :param range_low: The lowest address to allocate in a range
        :param range_high: The highest address to allocate in a range
        :param alloc_type: What sort of IP address to allocate in the
            range of choice in IPADDRESS_TYPE.
        :param user: If providing a user, the alloc_type must be
            IPADDRESS_TYPE.USER_RESERVED. Conversely, if the alloc_type is
            IPADDRESS_TYPE.USER_RESERVED the user must also be provided.
            AssertionError is raised if these conditions are not met.
        :param requested_address: Optional IP address that the caller wishes
            to use instead of being allocated one at random.

        All IP parameters can be strings or netaddr.IPAddress.

        Note: This method is inherently racy and depends on database
            serialisation to catch conflicts.  The caller should catch
            ValidationError exceptions and retry in this case.
        """
        if alloc_type == IPADDRESS_TYPE.USER_RESERVED and user is None:
            raise AssertionError(
                "Must provide user for USER_RESERVED alloc_type.")
        if user is not None and alloc_type != IPADDRESS_TYPE.USER_RESERVED:
            raise AssertionError(
                "Must not provide user for USER_RESERVED alloc_type.")
        # Convert args to strings if they are not already.
        if isinstance(range_low, IPAddress):
            range_low = range_low.ipv4().format()
        if isinstance(range_high, IPAddress):
            range_high = range_high.ipv4().format()
        if isinstance(requested_address, IPAddress):
            requested_address = requested_address.format()

        static_range = IPRange(range_low, range_high)
        if (requested_address is not None and
                IPAddress(requested_address) not in static_range):
            raise StaticIPAddressOutOfRange(
                "%s is not inside the range %s to %s" % (
                    requested_address, range_low, range_high))

        # When we do ipv6, this needs changing.
        range_list = [ip.ipv4().format() for ip in static_range]

        existing = self.filter(ip__gte=range_low, ip__lte=range_high)

        # Calculate the set of available IPs.  This will be inefficient
        # with large sets, but it will do for now.
        available = set(range_list) - set([addr.ip for addr in existing])

        # Try to allocate the IP.
        if requested_address is not None:
            self._get_specific_ip_from_set(available, requested_address)
            ip = requested_address
        else:
            ip = self._get_random_ip_from_set(available)

        # Convert to a StaticIPAddress record and return that.
        ipaddress = StaticIPAddress(
            ip=ip.format(), alloc_type=alloc_type, user=user)
        ipaddress.save()
        return ipaddress

    def _get_specific_ip_from_set(self, ips, requested_address):
        try:
            ips.remove(requested_address)
        except KeyError:
            raise StaticIPAddressUnavailable()

    def _get_random_ip_from_set(self, ips):
        # Return the first one available.  Should there be a period
        # where old addresses are not reallocated?
        # Other algorithms could be random, or round robin.
        try:
            ip = ips.pop()
        except KeyError:
            raise StaticIPAddressExhaustion()
        return ip

    def _deallocate(self, filter):
        """Helper func to deallocate the records in the supplied queryset
        filter and return a list of IPs deleted."""
        deallocated_ips = [record.ip.format() for record in filter]
        filter.delete()
        return deallocated_ips

    def deallocate_by_node(self, node):
        """Given a node, deallocate all of its AUTO StaticIPAddresses."""
        qs = self.filter(
            alloc_type=IPADDRESS_TYPE.AUTO).filter(
            macaddress__node=node)
        return self._deallocate(qs)

    def delete_by_node(self, node):
        """Given a node, delete ALL of its StaticIPAddresses.

        Unlike `deallocate_by_node`, which only removes AUTO IPs,
        this will delete every single IP associated with the node.
        """
        qs = self.filter(macaddress__node=node)
        return self._deallocate(qs)

    def get_hostname_ip_mapping(self, nodegroup):
        """Return a mapping {hostnames -> ips} for current `StaticIPAddress`es
        for the nodes in `nodegroup`.

        Any domain will be stripped from the hostnames.
        """
        cursor = connection.cursor()

        # DISTINCT ON returns the first matching row for any given
        # hostname, using the query's ordering.  Here, we're trying to
        # return the IP for the oldest MAC address.
        cursor.execute("""
            SELECT DISTINCT ON (node.hostname)
                node.hostname, staticip.ip
            FROM maasserver_macaddress AS mac
            JOIN maasserver_node AS node ON
                node.id = mac.node_id
            JOIN maasserver_macstaticipaddresslink AS link ON
                link.mac_address_id = mac.id
            JOIN maasserver_staticipaddress AS staticip ON
                staticip.id = link.ip_address_id
            WHERE node.nodegroup_id = %s
            ORDER BY node.hostname, mac.id
            """, (nodegroup.id,))
        return dict(
            (strip_domain(hostname), ip)
            for hostname, ip in cursor.fetchall()
            )


class StaticIPAddress(CleanSave, TimestampedModel):

    class Meta(DefaultMeta):
        verbose_name = "Static IP Address"
        verbose_name_plural = "Static IP Addresses"

    ip = MAASIPAddressField(
        unique=True, null=False, editable=False, blank=False,
        verbose_name='IP')

    # The MACStaticIPAddressLink table is used to link StaticIPAddress to
    # MACAddress.  See MACAddress.ip_addresses, and the reverse relation
    # self.macaddress_set (which will only ever contain one MAC due to
    # the unique FK restriction on the link table).

    alloc_type = IntegerField(
        editable=False, null=False, blank=False, default=IPADDRESS_TYPE.AUTO)

    user = ForeignKey(
        User, default=None, blank=True, null=True, editable=False)

    objects = StaticIPAddressManager()

    def __unicode__(self):
        # Attempt to show the symbolic alloc_type name if possible.

        # __iter__ does not work here for some reason, so using
        # iteritems().
        # XXX: convert this into a reverse_map_enum in maasserver.utils.
        for k, v in IPADDRESS_TYPE.__dict__.iteritems():
            if v == self.alloc_type:
                strtype = k
                break
        else:
            # Should never get here, but defensive coding FTW.
            strtype = "%s" % self.alloc_type
        return "<StaticIPAddress: <%s:type=%s>>" % (self.ip, strtype)

    def deallocate(self):
        """Mark this IP address as no longer in use.

        After return, this object is no longer valid.
        """
        self.delete()
