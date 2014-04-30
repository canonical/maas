# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Models for boot resource sources."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootSource',
    'BootSourceSelection',
    ]


from django.core.exceptions import ValidationError
from django.db.models import (
    BinaryField,
    CharField,
    FilePathField,
    ForeignKey,
    Manager,
    URLField,
    )
import djorm_pgarray.fields
from maasserver import DefaultMeta
from maasserver.enum import (
    DISTRO_SERIES,
    DISTRO_SERIES_CHOICES,
    )
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class BootSourceManager(Manager):
    """Manager for `BootSource` class."""


class BootSource(CleanSave, TimestampedModel):
    """A source for boot resources."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = BootSourceManager()

    cluster = ForeignKey(
        'maasserver.NodeGroup', editable=True, null=True, blank=False)

    url = URLField(blank=False, help_text="The URL of the BootSource.")

    keyring_filename = FilePathField(
        blank=True,
        help_text="The path to the keyring file for this BootSource.")

    keyring_data = BinaryField(
        blank=True,
        help_text="The GPG keyring  for this BootSource, as a binary blob.")

    def clean(self, *args, **kwargs):
        super(BootSource, self).clean(*args, **kwargs)

        # You have to specify one of {keyring_data, keyring_filename}.
        if len(self.keyring_filename) == 0 and len(self.keyring_data) == 0:
            raise ValidationError(
                "One of keyring_data or keyring_filename must be specified.")

        # You can have only one of {keyring_filename, keyring_data}; not
        # both.
        if len(self.keyring_filename) > 0 and len(self.keyring_data) > 0:
            raise ValidationError(
                "Only one of keyring_filename or keyring_data can be "
                "specified.")


class BootSourceSelectionManager(Manager):
    """Manager for `BootSourceSelection` class."""


class BootSourceSelection(CleanSave, TimestampedModel):
    """A set of selections for a single `BootSource`."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = BootSourceSelectionManager()

    boot_source = ForeignKey('maasserver.BootSource', blank=False)

    release = CharField(
        max_length=20, choices=DISTRO_SERIES_CHOICES, blank=True,
        default=DISTRO_SERIES.default,
        help_text="The Ubuntu release for which to import resources.")

    arches = djorm_pgarray.fields.ArrayField(dbtype="text")

    subarches = djorm_pgarray.fields.ArrayField(dbtype="text")

    labels = djorm_pgarray.fields.ArrayField(dbtype="text")
