# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RegionRackRPCConnection object."""

from django.db.models import CASCADE, ForeignKey

from maasserver.models.cleansave import CleanSave
from maasserver.models.node import RackController
from maasserver.models.regioncontrollerprocessendpoint import (
    RegionControllerProcessEndpoint,
)
from maasserver.models.timestampedmodel import TimestampedModel


class RegionRackRPCConnection(CleanSave, TimestampedModel):
    """`RegionRackRPCConnection` records a connection between a region
    controller and rack controller within the MAAS communication strucutre.

    This is used by the region controller to inform a user when a connection
    between a region controller and rack controller are missing. This is also
    used by the "sys_connection_{region_id}" notification event in the database
    to inform a region controller that it needs to manage a rack controller.

    :ivar endpoint: `RegionControllerProcessEndpoint` endpoint the rack
        controller connected to.
    :ivar rack_controller: `RackController` this connection goes to.
    """

    class Meta:
        unique_together = ("endpoint", "rack_controller")

    endpoint = ForeignKey(
        RegionControllerProcessEndpoint,
        null=False,
        blank=False,
        related_name="connections",
        on_delete=CASCADE,
    )
    rack_controller = ForeignKey(
        RackController,
        null=False,
        blank=False,
        related_name="connections",
        on_delete=CASCADE,
    )
