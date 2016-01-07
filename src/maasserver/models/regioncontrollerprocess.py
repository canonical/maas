# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RegionControllerProcess object."""

__all__ = [
    "RegionControllerProcess",
    ]

from django.db.models import (
    ForeignKey,
    IntegerField,
)
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.node import RegionController
from maasserver.models.timestampedmodel import TimestampedModel


class RegionControllerProcess(CleanSave, TimestampedModel):
    """A `RegionControllerProcess` that is running on a `RegionController`.

    :ivar region: `RegionController` the process is running on.
    :ivar pid: Process ID for the process.
    """

    class Meta(DefaultMeta):
        """Needed recognize this model."""
        unique_together = ("region", "pid")
        ordering = ["pid"]

    region = ForeignKey(
        RegionController, null=False, blank=False, related_name="processes")
    pid = IntegerField()
