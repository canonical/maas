# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for networks."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Network',
    ]


from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    GenericIPAddressField,
    Model,
    PositiveSmallIntegerField,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave


class Network(CleanSave, Model):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    name = CharField(
        unique=True, blank=False, editable=True, max_length=255,
        help_text="Identifying name for this network.")

    ip = GenericIPAddressField(
        blank=False, editable=True, unique=True, null=False,
        help_text="Lowest IP address of this network.")

    netmask = GenericIPAddressField(
        blank=False, editable=True, null=False,
        help_text="Network mask (e.g. 255.255.255.0).")

    vlan_tag = PositiveSmallIntegerField(
        editable=True, blank=False, unique=True,
        help_text="A 12-bit field specifying the VLAN to which the frame "
                  "belongs. The hexadecimal values of 0x000 and 0xFFF "
                  "are reserved. All other values may be used as VLAN "
                  "identifiers, allowing up to 4,094 VLANs. The reserved "
                  "value 0x000 indicates that the frame does not belong "
                  "to any VLAN; in this case, the 802.1Q tag specifies "
                  "only a priority and is referred to as a priority tag. "
                  "On bridges, VLAN 1 (the default VLAN ID) is often "
                  "reserved for a management VLAN; this is vendor-"
                  "specific.")

    description = CharField(
        max_length=255, default='', blank=True, editable=True,
        help_text="Any short description to help users identify the network")

    def clean_vlan_tag(self):
        if self.vlan_tag == 0xFFF:
            raise ValidationError(
                {'tag': ["Cannot use reserved value 0xFFF."]})
        if self.vlan_tag < 0 or self.vlan_tag > 0xFFF:
            raise ValidationError(
                {'tag': ["Value must be between 0x000 and 0xFFF (12 bits)"]})

    def clean_fields(self, *args, **kwargs):
        super(Network, self).clean_fields(*args, **kwargs)
        self.clean_vlan_tag()
