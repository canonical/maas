# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for NodeGroupInterface."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'NodeGroupInterface',
    ]


from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    IPAddressField,
    )
from maasserver import DefaultMeta
from maasserver.enum import (
    NODEGROUPINTERFACE_MANAGEMENT,
    NODEGROUPINTERFACE_MANAGEMENT_CHOICES,
    )
from maasserver.models.timestampedmodel import TimestampedModel


class NodeGroupInterface(TimestampedModel):

    class Meta(DefaultMeta):
        unique_together = ('nodegroup', 'interface')

    # Static IP of the interface.
    ip = IPAddressField(null=False, editable=True)

    # The `NodeGroup` this interface belongs to.
    nodegroup = ForeignKey(
        'maasserver.NodeGroup', editable=True, null=False, blank=False)

    management = IntegerField(
        choices=NODEGROUPINTERFACE_MANAGEMENT_CHOICES, editable=False,
        default=NODEGROUPINTERFACE_MANAGEMENT.DEFAULT_STATUS)

    # DHCP server settings.
    interface = CharField(
        blank=True, editable=False, max_length=255, default='')
    subnet_mask = IPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    broadcast_ip = IPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    router_ip = IPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    ip_range_low = IPAddressField(
        editable=True, unique=True, blank=True, null=True, default=None)
    ip_range_high = IPAddressField(
        editable=True, unique=True, blank=True, null=True, default=None)

    def __repr__(self):
        return "<NodeGroupInterface %r,%s>" % (self.nodegroup, self.interface)
