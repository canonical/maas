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
    GenericIPAddressField,
    IntegerField,
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
    ip = GenericIPAddressField(null=False, editable=True)

    # The `NodeGroup` this interface belongs to.
    nodegroup = ForeignKey(
        'maasserver.NodeGroup', editable=True, null=False, blank=False)

    management = IntegerField(
        choices=NODEGROUPINTERFACE_MANAGEMENT_CHOICES, editable=True,
        default=NODEGROUPINTERFACE_MANAGEMENT.DEFAULT)

    # DHCP server settings.
    interface = CharField(
        blank=True, editable=True, max_length=255, default='')
    subnet_mask = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    broadcast_ip = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    router_ip = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    ip_range_low = GenericIPAddressField(
        editable=True, unique=True, blank=True, null=True, default=None)
    ip_range_high = GenericIPAddressField(
        editable=True, unique=True, blank=True, null=True, default=None)

    def __repr__(self):
        return "<NodeGroupInterface %r,%s>" % (self.nodegroup, self.interface)
