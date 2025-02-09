# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for filtering a selection of boot resources."""

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import CASCADE, CharField, ForeignKey, Manager, TextField

from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.timestampedmodel import TimestampedModel


class BootSourceSelectionManager(Manager):
    """Manager for `BootSourceSelection` class."""


class BootSourceSelection(CleanSave, TimestampedModel):
    """A set of selections for a single `BootSource`."""

    class Meta:
        unique_together = ("boot_source", "os", "release")

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

    arches = ArrayField(TextField(), blank=True, null=True, default=list)

    subarches = ArrayField(TextField(), blank=True, null=True, default=list)

    labels = ArrayField(TextField(), blank=True, null=True, default=list)

    def to_dict(self):
        """Return the current `BootSourceSelection` as a dict."""
        return {
            "os": self.os,
            "release": self.release,
            "arches": self.arches,
            "subarches": self.subarches,
            "labels": self.labels,
        }

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
                "Unable to delete %s %s. "
                "It is the operating system used in ephemeral environments."
            )
        else:
            return super().delete(*args, **kwargs)
