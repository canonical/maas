# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for filtering a selection of boot resources."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootSourceSelection',
    ]


from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
    )
import djorm_pgarray.fields
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS


def list_release_choices():
    """Return Django "choices" list for Ubuntu releases."""
    osystem = UbuntuOS()
    releases = osystem.get_supported_releases()
    return osystem.format_release_choices(releases)


class BootSourceSelectionManager(Manager):
    """Manager for `BootSourceSelection` class."""


class BootSourceSelection(CleanSave, TimestampedModel):
    """A set of selections for a single `BootSource`."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = BootSourceSelectionManager()

    boot_source = ForeignKey('maasserver.BootSource', blank=False)

    release = CharField(
        max_length=20, choices=list_release_choices(), blank=True,
        default='',
        help_text="The Ubuntu release for which to import resources.")

    arches = djorm_pgarray.fields.ArrayField(dbtype="text")

    subarches = djorm_pgarray.fields.ArrayField(dbtype="text")

    labels = djorm_pgarray.fields.ArrayField(dbtype="text")

    def to_dict(self):
        """Return the current `BootSourceSelection` as a dict."""
        return {
            "release": self.release,
            "arches": self.arches,
            "subarches": self.subarches,
            "labels": self.labels,
            }
