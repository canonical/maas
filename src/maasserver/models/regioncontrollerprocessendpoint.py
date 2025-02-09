# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RegionControllerProcessEndpoint object."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import (
    CASCADE,
    ForeignKey,
    GenericIPAddressField,
    IntegerField,
)

from maasserver.models.cleansave import CleanSave
from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.timestampedmodel import TimestampedModel


class RegionControllerProcessEndpoint(CleanSave, TimestampedModel):
    """`RegionControllerProcessEndpoint` is a RPC endpoint on the
    `RegionControllerProcess` one endpoint is created per IP address on the
    `RegionControllerProcess`.

    :ivar process: `RegionControllerProcess` for this endpoint.
    :ivar address: IP address for the endpoint.
    :ivar port: Port number of the endpoint.
    """

    class Meta:
        unique_together = ("process", "address", "port")

    process = ForeignKey(
        RegionControllerProcess,
        null=False,
        blank=False,
        related_name="endpoints",
        on_delete=CASCADE,
    )
    address = GenericIPAddressField(null=False, blank=False, editable=False)
    port = IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(65535)]
    )
