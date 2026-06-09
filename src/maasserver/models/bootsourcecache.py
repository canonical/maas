# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for a cache of images available in a boot source."""

from django.db.models import (
    CASCADE,
    CharField,
    DateField,
    ForeignKey,
    JSONField,
)

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class BootSourceCache(CleanSave, TimestampedModel):
    """A cache of an image provided in boot source."""

    boot_source = ForeignKey(
        "maasserver.BootSource", blank=False, on_delete=CASCADE
    )

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
