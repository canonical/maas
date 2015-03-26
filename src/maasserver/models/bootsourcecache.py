# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a cache of images available in a boot source."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootSourceCache',
    ]


from django.db.models import (
    CharField,
    ForeignKey,
)
from maasserver import DefaultMeta
from maasserver.models.bootsource import BootSource
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class BootSourceCache(CleanSave, TimestampedModel):
    """A cache of an image provided in boot source."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    boot_source = ForeignKey(BootSource, blank=False)

    os = CharField(max_length=20, blank=False, null=False)

    arch = CharField(max_length=20, blank=False, null=False)

    subarch = CharField(max_length=20, blank=False, null=False)

    release = CharField(max_length=20, blank=False, null=False)

    label = CharField(max_length=20, blank=False, null=False)
