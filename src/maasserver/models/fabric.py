# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fabric objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DEFAULT_FABRIC_NAME",
    "Fabric",
    "FABRIC_NAME_VALIDATOR",
    ]

import datetime

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
)
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


FABRIC_NAME_VALIDATOR = RegexValidator('^[ \w-]+$')

# Name of the special, default fabric.  This fabric cannot be deleted.
DEFAULT_FABRIC_NAME = 'Default fabric'


class FabricManager(Manager):
    """Manager for :class:`Fabric` model."""

    def get_default_fabric(self):
        """Return the default fabric."""
        now = datetime.datetime.now()
        fabric, _ = self.get_or_create(
            id=0,
            defaults={
                'id': 0,
                'name': DEFAULT_FABRIC_NAME,
                'created': now,
                'updated': now,
            }
        )
        return fabric


class Fabric(CleanSave, TimestampedModel):
    """A `Fabric`.

    :ivar name: The short-human-identifiable name for this fabric.
    :ivar objects: An instance of the class :class:`FabricManager`.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "Fabric"
        verbose_name_plural = "Fabrics"

    objects = FabricManager()

    name = CharField(
        max_length=256, unique=True, editable=True,
        validators=[FABRIC_NAME_VALIDATOR])

    default_vlan = ForeignKey(
        'VLAN', blank=True, null=True, editable=True, related_name='+')

    def __unicode__(self):
        return "name=%s" % self.name

    def is_default(self):
        """Is this the default fabric?"""
        return self.id == 0

    def clean(self, *args, **kwargs):
        wrong_fabric = (
            self.default_vlan_id is not None and
            self.default_vlan.fabric != self)
        if wrong_fabric:
            raise ValidationError(
                {'default_vlan':
                    ["Can't set a default VLAN that's not in this fabric."]})
        super(Fabric, self).clean(*args, **kwargs)

    def delete(self):
        if self.is_default():
            raise ValidationError(
                "This fabric is the default fabric, it cannot be deleted.")
        super(Fabric, self).delete()

    def save(self, *args, **kwargs):
        created = self.id is None
        super(Fabric, self).save(*args, **kwargs)
        # Create default VLAN if this is a fabric creation.
        if created:
            from maasserver.models.vlan import (
                VLAN, DEFAULT_VLAN_NAME, DEFAULT_VID)
            default_vlan = VLAN.objects.create(
                name=DEFAULT_VLAN_NAME, vid=DEFAULT_VID, fabric=self)
            self.default_vlan = default_vlan
            self.save()
