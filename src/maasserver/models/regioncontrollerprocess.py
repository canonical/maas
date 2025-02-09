# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RegionControllerProcess object."""

from django.db.models import CASCADE, ForeignKey, IntegerField

from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import TimestampedModel


class RegionControllerProcess(CleanSave, TimestampedModel):
    """A `RegionControllerProcess` that is running on a `RegionController` or
    `RegionRackController`.

    :ivar region: `RegionController` or `RegionRackController` the process is
        running on.
    :ivar pid: Process ID for the process.
    """

    class Meta:
        unique_together = ("region", "pid")
        ordering = ["pid"]

    # It links to `Node` but it will be either
    # `RegionController` or `RegionRackController`.
    region = ForeignKey(
        Node,
        null=False,
        blank=False,
        related_name="processes",
        on_delete=CASCADE,
    )

    pid = IntegerField()
