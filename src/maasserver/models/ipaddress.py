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


from django.db.models import (
    GenericIPAddressField,
    IntegerField,
    )
from maasserver import DefaultMeta
from maasserver.enum import IPADDRESS_TYPE
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


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

    def __unicode__(self):
        return "<IPAddress %s>" % self.ip
