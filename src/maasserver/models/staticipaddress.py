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
    'StaticIPAddressExhaustion',
    ]


from django.db.models import (
    GenericIPAddressField,
    IntegerField,
    Manager,
    )
from maasserver import DefaultMeta
from maasserver.enum import IPADDRESS_TYPE
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from netaddr import (
    IPAddress,
    IPRange,
    )


class StaticIPAddressExhaustion(Exception):
    """Raised when no more static IPs are available during allocation."""


class StaticIPAddressManager(Manager):
    """A utility to manage collections of IPAddresses."""

    def allocate_new(self, range_low, range_high,
                     alloc_type=IPADDRESS_TYPE.AUTO):
        """Return a new StaticIPAddress.

        :param range_low: The lowest address to allocate in a range
        :param range_high: The highest address to allocate in a range

        The range parameters can be strings or netaddr.IPAddress.

        Note: This method is inherently racy and depends on database
            serialisation to catch conflicts.  The caller should catch
            ValidationError exceptions and retry in this case.
        """
        # Convert args to strings if they are not already.
        if isinstance(range_low, IPAddress):
            range_low = range_low.ipv4().format()
        if isinstance(range_high, IPAddress):
            range_high = range_high.ipv4().format()

        static_range = IPRange(range_low, range_high)
        # When we do ipv6, this needs changing.
        range_list = [ip.ipv4().format() for ip in static_range]
        existing = self.filter(ip__gte=range_low, ip__lte=range_high)

        # Calculate the set of available IPs.  This will be inefficient
        # with large sets, but it will do for now.
        available = set(range_list) - set([addr.ip for addr in existing])

        # Return the first one available.  Should there be a period
        # where old addresses are not reallocated?
        # Other algorithms could be random, or round robin.
        try:
            ip = available.pop()
        except KeyError:
            raise StaticIPAddressExhaustion()

        ipaddress = StaticIPAddress(ip=ip.format(), alloc_type=alloc_type)
        ipaddress.save()
        return ipaddress


class StaticIPAddress(CleanSave, TimestampedModel):

    class Meta(DefaultMeta):
        verbose_name = "Static IP Address"
        verbose_name_plural = "Static IP Addresses"

    ip = GenericIPAddressField(
        unique=True, null=False, editable=False, blank=False)

    # The MACIPAddressLink table is used to link IPAddress to
    # MACAddress.  See MACAddress.ip_addresses.

    alloc_type = IntegerField(
        editable=False, null=False, blank=False, default=IPADDRESS_TYPE.AUTO)

    objects = StaticIPAddressManager()

    def __unicode__(self):
        return "<IPAddress %s>" % self.ip
