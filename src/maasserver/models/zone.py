# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Physical zone objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DEFAULT_ZONE_NAME",
    "Zone",
    "ZONE_NAME_VALIDATOR",
    ]

import datetime

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    Manager,
    TextField,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


ZONE_NAME_VALIDATOR = RegexValidator('^[\w-]+$')

# Name of the special, default zone.  This zone can be neither deleted nor
# renamed.
DEFAULT_ZONE_NAME = 'default'


class ZoneManager(Manager):
    """Manager for :class:`Zone` model.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def get_default_zone(self):
        """Return the default zone."""
        now = datetime.datetime.now()
        zone, _ = self.get_or_create(
            name=DEFAULT_ZONE_NAME,
            defaults={
                'name': DEFAULT_ZONE_NAME,
                'created': now,
                'updated': now,
            }
        )
        return zone


class Zone(CleanSave, TimestampedModel):
    """A `Zone` is an entity used to logically group nodes together.

    :ivar name: The short-human-identifiable name for this zone.
    :ivar description: Free-form description for this zone.
    :ivar objects: An instance of the class :class:`ZoneManager`.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "Physical zone"
        verbose_name_plural = "Physical zones"
        ordering = ["name"]

    objects = ZoneManager()

    name = CharField(
        max_length=256, unique=True, editable=True,
        validators=[ZONE_NAME_VALIDATOR])

    description = TextField(blank=True, editable=True)

    def __unicode__(self):
        return self.name

    def is_default(self):
        """Is this the default zone?"""
        return self.name == DEFAULT_ZONE_NAME

    def delete(self):
        if self.is_default():
            raise ValidationError(
                "This zone is the default zone, it cannot be deleted.")
        super(Zone, self).delete()
