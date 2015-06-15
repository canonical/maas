# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for MACIPAddressLink.

Maintains a relationship between MACAddress and IPAddress.  This is defined
instead of using Django's auto-generated link table because it also contains
additional metadata about the link, such as a NIC alias.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'MACStaticIPAddressLink',
    ]


from django.db.models import (
    ForeignKey,
    IntegerField,
)
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class MACStaticIPAddressLink(CleanSave, TimestampedModel):

    # XXX:fabric IP addresses are unique within each fabric, so this
    # code needs to be updated.
    class Meta(DefaultMeta):
        unique_together = ('ip_address', 'mac_address')

    mac_address = ForeignKey('maasserver.MACAddress')
    ip_address = ForeignKey('maasserver.StaticIPAddress', unique=True)

    # Optional NIC alias for multi-homed NICs (e.g. 'eth0:1')
    nic_alias = IntegerField(
        editable=True, null=True, blank=True, default=None)
