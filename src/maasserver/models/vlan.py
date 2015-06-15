# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""VLAN objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DEFAULT_VID",
    "DEFAULT_VLAN_NAME",
    "Fabric",
    ]


from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
)
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.fabric import Fabric
from maasserver.models.timestampedmodel import TimestampedModel


VLAN_NAME_VALIDATOR = RegexValidator('^[ \w-]+$')

DEFAULT_VLAN_NAME = 'Default VLAN'
DEFAULT_VID = 0


class VLAN(CleanSave, TimestampedModel):
    """A `VLAN`.

    :ivar name: The short-human-identifiable name for this VLAN.
    :ivar vid: The VLAN ID of this VLAN.
    :ivar fabric: The `Fabric` this VLAN belongs to.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "VLAN"
        verbose_name_plural = "VLANs"
        unique_together = (
            ('vid', 'fabric'),
            ('name', 'fabric'),
        )

    name = CharField(
        max_length=256, editable=True, validators=[VLAN_NAME_VALIDATOR])

    vid = IntegerField(editable=True)

    fabric = ForeignKey(
        'Fabric', blank=False, editable=True)

    def __unicode__(self):
        return "name=%s, vid=%d, fabric=%s" % (
            self.name, self.vid, self.fabric.name)

    def clean_vid(self):
        if self.vid < 0 or self.vid > 4095:
            raise ValidationError(
                {'vid':
                    ["Vid must be between 0 and 4095."]})

    def clean(self):
        self.clean_vid()

    def is_fabric_default(self):
        """Is this the default VLAN in the fabric?"""
        return self.fabric.default_vlan == self
