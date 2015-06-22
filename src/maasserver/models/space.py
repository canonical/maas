# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Space objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DEFAULT_SPACE_NAME",
    "Space",
    "SPACE_NAME_VALIDATOR",
    ]

import datetime

from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    Manager,
)
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


SPACE_NAME_VALIDATOR = RegexValidator('^[ \w-]+$')

# Name of the special, default space.  This space cannot be deleted.
DEFAULT_SPACE_NAME = 'Default space'


class SpaceManager(Manager):
    """Manager for :class:`Space` model."""

    def get_default_space(self):
        """Return the default space."""
        now = datetime.datetime.now()
        space, _ = self.get_or_create(
            id=0,
            defaults={
                'id': 0,
                'name': DEFAULT_SPACE_NAME,
                'created': now,
                'updated': now,
            }
        )
        return space


class Space(CleanSave, TimestampedModel):
    """A `Space`.

    :ivar name: The short-human-identifiable name for this space.
    :ivar objects: An instance of the class :class:`SpaceManager`.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "Space"
        verbose_name_plural = "Spaces"

    objects = SpaceManager()

    name = CharField(
        max_length=256, unique=True, editable=True,
        validators=[SPACE_NAME_VALIDATOR])

    def __unicode__(self):
        return "name=%s" % self.name

    def is_default(self):
        """Is this the default space?"""
        return self.id == 0
