# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for filtering a selection of boot resources."""

from django.core.exceptions import ValidationError
from django.db.models import CASCADE, CharField, ForeignKey, Manager, TextField

from maasserver.models.bootresource import BootResource
from maasserver.models.bootresourcefile import BootResourceFile
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.timestampedmodel import TimestampedModel


class BootSourceSelectionManager(Manager):
    """Manager for `BootSourceSelection` class."""


class BootSourceSelection(CleanSave, TimestampedModel):
    """A set of selections for a single `BootSource`."""

    class Meta:
        unique_together = ("boot_source", "os", "release", "arch")

    objects = BootSourceSelectionManager()

    boot_source = ForeignKey(
        "maasserver.BootSource", blank=False, on_delete=CASCADE
    )

    os = CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="The operating system for which to import resources.",
    )

    release = CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="The OS release for which to import resources.",
    )

    arch = TextField(blank=False, null=False)

    def to_dict(self):
        """Return the current `BootSourceSelection` as a dict."""
        return {
            "os": self.os,
            "release": self.release,
            "arch": self.arch,
        }

    def force_delete(self):
        """Delete without checking if this selection is the one used for commissioning."""
        boot_resources_to_delete = BootResource.objects.filter(
            boot_source_selection=self
        )
        BootResourceFile.objects.filestore_remove_resources(
            boot_resources_to_delete
        )
        boot_resources_to_delete.delete()
        return super().delete()

    def delete(self, *args, **kwargs):
        commissioning_osystem = Config.objects.get_config(
            name="commissioning_osystem"
        )
        commissioning_series = Config.objects.get_config(
            name="commissioning_distro_series"
        )
        if (
            commissioning_osystem == self.os
            and commissioning_series == self.release
        ):
            raise ValidationError(
                f"Unable to delete {self.os} {self.release}. "
                "It is the operating system used for commissioning."
            )
        else:
            return self.force_delete()
