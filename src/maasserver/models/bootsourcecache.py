# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a cache of images available in a boot source."""


from django.db.models import (
    CASCADE,
    CharField,
    DateField,
    ForeignKey,
    JSONField,
    Manager,
)

from maasserver.models.bootsource import BootSource
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class BootSourceCacheManager(Manager):
    def get_release_title(self, os, release):
        """Return the release title."""
        cache = (
            self.filter(os=os, release=release)
            .exclude(release_title__isnull=True, release_title__exact="")
            .first()
        )
        if cache is None:
            return None
        else:
            return cache.release_title

    def get_release_codename(self, os, release):
        """Return the release codename."""
        cache = (
            self.filter(os=os, release=release)
            .exclude(release_codename__isnull=True, release_codename__exact="")
            .first()
        )
        if cache is None:
            return None
        else:
            return cache.release_codename


class BootSourceCache(CleanSave, TimestampedModel):
    """A cache of an image provided in boot source."""

    objects = BootSourceCacheManager()

    boot_source = ForeignKey(BootSource, blank=False, on_delete=CASCADE)

    os = CharField(max_length=32, blank=False, null=False)

    bootloader_type = CharField(max_length=32, blank=True, null=True)

    arch = CharField(max_length=32, blank=False, null=False)

    subarch = CharField(max_length=32, blank=False, null=False)

    kflavor = CharField(max_length=32, blank=True, null=True)

    release = CharField(max_length=32, blank=False, null=False)

    label = CharField(max_length=32, blank=False, null=False)

    release_codename = CharField(max_length=255, blank=True, null=True)

    release_title = CharField(max_length=255, blank=True, null=True)

    support_eol = DateField(null=True, blank=True)

    extra = JSONField(blank=True, default=dict)

    def __str__(self):
        return (
            "<BootSourceCache os=%s, release=%s, arch=%s, subarch=%s, "
            "kflavor=%s>"
            % (self.os, self.release, self.arch, self.subarch, self.kflavor)
        )
