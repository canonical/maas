# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for reserved IPs.

The ReservedIP model allows a user to reserve an IP for a specific purpose.
The IP:
- remains reserved unless the user release it,
- can be linked to a mac address,
- is associated to a subnet and vlan accessible by MAAS,
- if the subnet and vlan are not provided, the model will try to identify the
  best fit for the given IP.
"""
from __future__ import annotations

from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Manager,
    TextField,
    UniqueConstraint,
)
from django.db.models.fields import GenericIPAddressField

from maasserver.fields import MAC_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin


class ReservedIPManager(Manager, MAASQueriesMixin):
    """Manager of the ReservedIP model.

    As (Django) manager, this class interfaces with the ReservedIp model in the
    database.
    """

    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
        }
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs,
        )

    def get_reserved_ip_or_404(self, reserved_ip_id: int) -> ReservedIP:
        """Gets a reserved IP using the given it is ID.

        If the ID is not provided ("" or None), raises HTTP 400.
        If multiple objects are returned, raises HTTP 403.
        If the reserved IP cannot be found, raises HTTP 404.
        """
        reserved_ip = self.get_object_by_specifiers_or_raise(reserved_ip_id)
        return reserved_ip


class ReservedIP(CleanSave, TimestampedModel):
    """Reserved IP model.

    As (Django) model, this class contains the fields and behaviours of the
    reserved IPs data.
    """

    objects = ReservedIPManager()

    subnet = ForeignKey(
        "Subnet", editable=True, blank=False, null=False, on_delete=CASCADE
    )

    ip = GenericIPAddressField(
        null=False,
        editable=True,
        blank=False,
        unique=True,
        verbose_name="IP address",
    )

    mac_address = TextField(
        null=False,
        editable=True,
        blank=False,
        validators=[MAC_VALIDATOR],
        verbose_name="MAC address",
    )

    comment = CharField(
        max_length=255, null=True, blank=True, editable=True, default=""
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["mac_address", "subnet"],
                name="maasserver_reservedip_mac_address_subnet_uniq",
            ),
        ]
        verbose_name = "Reserved IP"

    def __str__(self):
        fields = [
            f"{self.ip} ({str(self.subnet.cidr)})",
            self.mac_address,
            self.comment,
        ]
        return ", ".join(filter(None, fields))
