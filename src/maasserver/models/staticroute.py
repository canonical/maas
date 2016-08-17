# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Static route between two subnets using a gateway."""

__all__ = [
    'StaticRoute',
    ]


from django.core.exceptions import ValidationError
from django.db.models import (
    ForeignKey,
    Model,
    PositiveIntegerField,
)
from maasserver import DefaultMeta
from maasserver.fields import MAASIPAddressField
from maasserver.models.cleansave import CleanSave


class StaticRoute(CleanSave, Model):
    """Static route between two subnets using a gateway."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        unique_together = ('source', 'destination', 'gateway_ip')

    source = ForeignKey(
        'Subnet', blank=False, null=False, related_name="+")

    destination = ForeignKey(
        'Subnet', blank=False, null=False, related_name="+")

    gateway_ip = MAASIPAddressField(
        unique=False, null=False, blank=False, editable=True,
        verbose_name='Gateway IP')

    metric = PositiveIntegerField(blank=False, null=False)

    def clean(self):
        if self.source == self.destination:
            raise ValidationError(
                "source and destination cannot be the same subnet.")
        source_network = self.source.get_ipnetwork()
        source_version = source_network.version
        destination_version = self.destination.get_ipnetwork().version
        if source_version != destination_version:
            raise ValidationError(
                "source and destination must be the same IP version.")
        if self.gateway_ip not in source_network:
            raise ValidationError(
                "gateway_ip must be with in the source subnet.")
