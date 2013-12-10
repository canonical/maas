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
    ]

from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    TextField,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class Zone(CleanSave, TimestampedModel):
    """A `Zone` is an entity used to logically group nodes together.

    :ivar name: The short-human-identifiable name for this zone.
    :ivar description: Free-form description for this zone.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "Availability zone"
        verbose_name_plural = "Availability zones"

    _zone_name_regex = '^[\w-]+$'

    name = CharField(
        max_length=256, unique=True, editable=True,
        validators=[RegexValidator(_zone_name_regex)])
    description = TextField(blank=True, editable=True)

    def __unicode__(self):
        return self.name
