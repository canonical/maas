# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for NodeGroup which models a collection of Nodes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'NodeGroup',
    ]


from django.db.models import (
    CharField,
    ForeignKey,
    IPAddressField,
    Manager,
    )
from maasserver import DefaultMeta
from maasserver.models.timestampedmodel import TimestampedModel
from piston.models import (
    KEY_SIZE,
    Token,
    )


class NodeGroupManager(Manager):
    """Manager for the NodeGroup class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """


class NodeGroup(TimestampedModel):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = NodeGroupManager()

    # Name for the node group's DNS zone.
    name = CharField(max_length=80, unique=True, editable=True, default="")

    api_token = ForeignKey(Token, null=False, editable=False, unique=True)
    api_key = CharField(
        max_length=KEY_SIZE, null=False, editable=False, unique=True)

    worker_ip = IPAddressField(null=False, editable=True, unique=True)

    subnet_mask = IPAddressField(null=False, editable=True, unique=False)

    broadcast_ip = IPAddressField(null=False, editable=True, unique=False)

    router_ip = IPAddressField(null=False, editable=True, unique=False)

    ip_range_low = IPAddressField(null=False, editable=True, unique=True)
    ip_range_high = IPAddressField(null=False, editable=True, unique=True)
