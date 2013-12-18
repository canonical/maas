# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Availability zone objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "Zone",
    "ZONE_NAME_VALIDATOR",
    ]

from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    TextField,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


ZONE_NAME_VALIDATOR = RegexValidator('^[\w-]+$')


class Zone(CleanSave, TimestampedModel):
    """A `Zone` is an entity used to logically group nodes together.

    :ivar name: The short-human-identifiable name for this zone.
    :ivar description: Free-form description for this zone.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "Availability zone"
        verbose_name_plural = "Availability zones"

    name = CharField(
        max_length=256, unique=True, editable=True,
        validators=[ZONE_NAME_VALIDATOR])
    description = TextField(blank=True, editable=True)

    def __unicode__(self):
        return self.name

    def delete(self):
        """Delete zone, but keep its nodes!

        Deleting a zone, by default, deletes all the nodes that are in that
        zone.  Use `delete` instead: it will clear those nodes' `zone` fields
        so they'll be zoneless, but not gone.
        """
        # Avoid circular imports.
        from maasserver.models.node import Node

        # Clear nodes' references to this zone.
        Node.objects.filter(zone=self).update(zone=None)
        # That being done, defer to the reckless default implementation.
        super(Zone, self).delete()
