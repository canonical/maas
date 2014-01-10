# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for VLANs"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Vlan',
    ]


from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    Manager,
    Model,
    PositiveSmallIntegerField,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave


class VlanManager(Manager):
    """Manager for Vlan model class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """


class Vlan(CleanSave, Model):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = VlanManager()

    tag = PositiveSmallIntegerField(
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
        help_text="Any short description to help users identify the VLAN")

    def clean_tag(self):
        if self.tag == 0x000 or self.tag == 0xFFF:
            raise ValidationError(
                {'tag': ["Cannot use reserved values 0x000 and 0xFFF"]})
        if self.tag < 0 or self.tag > 0xFFF:
            raise ValidationError(
                {'tag': ["Value must be between 0x000 and 0xFFF (12 bits)"]})

    def clean_fields(self, *args, **kwargs):
        super(Vlan, self).clean_fields(*args, **kwargs)
        self.clean_tag()
