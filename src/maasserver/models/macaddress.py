# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MACAddress model and friends."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'MACAddress',
    ]


import re

from django.db.models import ForeignKey
from maasserver import DefaultMeta
from maasserver.fields import MACAddressField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


mac_re = re.compile(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$')


class MACAddress(CleanSave, TimestampedModel):
    """A `MACAddress` represents a `MAC address
    <http://en.wikipedia.org/wiki/MAC_address>`_ attached to a :class:`Node`.

    :ivar mac_address: The MAC address.
    :ivar node: The `Node` related to this `MACAddress`.

    """
    mac_address = MACAddressField(unique=True)
    node = ForeignKey('Node', editable=False)

    class Meta(DefaultMeta):
        verbose_name = "MAC address"
        verbose_name_plural = "MAC addresses"

    def __unicode__(self):
        return self.mac_address

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ('mac_address',):
                return "This MAC address is already registered."
        return super(
            MACAddress, self).unique_error_message(model_class, unique_check)
