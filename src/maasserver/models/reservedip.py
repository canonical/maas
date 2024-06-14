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
from ipaddress import ip_address, ip_network

from django.core.exceptions import ValidationError
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Manager,
    PROTECT,
    TextField,
    UniqueConstraint,
)
from django.db.models.fields import GenericIPAddressField

from maasserver.fields import MAC_VALIDATOR
from maasserver.models.cleansave import CleanSave
from maasserver.models.subnet import Subnet
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import transactional


class ReservedIPManager(Manager):
    """Manager of the ReservedIP model.

    As (Django) manager, this class interfaces with the ReservedIp model in the
    database.
    """


class ReservedIP(CleanSave, TimestampedModel):
    """Reserved IP model.

    (Django) model containing the fields and behaviours of the reserved IPs
    data.
    """

    objects = ReservedIPManager()

    subnet = ForeignKey(
        "Subnet", editable=True, blank=False, null=False, on_delete=CASCADE
    )

    vlan = ForeignKey(
        "VLAN",
        editable=True,
        blank=False,
        null=False,
        on_delete=PROTECT,
        verbose_name="VLAN",
    )

    ip = GenericIPAddressField(
        null=False,
        editable=True,
        blank=False,
        unique=True,
        verbose_name="IP address",
        validators=[],
    )

    mac_address = TextField(
        null=True,
        blank=True,
        validators=[MAC_VALIDATOR],
        verbose_name="MAC address",
    )

    comment = CharField(
        max_length=255, null=True, blank=True, editable=True, default=""
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["mac_address", "vlan"],
                name="maasserver_reservedip_mac_address_vlan_uniq",
            ),
        ]
        verbose_name = "Reserved IP"

    def clean(self) -> None:
        super().clean()

        if ip := str(self.ip):
            try:
                ip = ip_address(ip)
                if hasattr(self, "subnet"):
                    net = ip_network(self.subnet.cidr)
                    if ip not in ip_network(self.subnet.cidr):
                        raise ValidationError(
                            {
                                (
                                    "ip",
                                    "subnet",
                                ): "The provided IP is not part of any available subnet."
                            }
                        )
                    if ip == net.network_address:
                        raise ValidationError(
                            {
                                "ip": "The network address cannot be a reserved IP."
                            }
                        )
                    if ip == net.broadcast_address:
                        raise ValidationError(
                            {
                                "ip": "The broadcast address cannot be a reserved IP."
                            }
                        )
            except ValueError:
                # if IP is None, a validation error is raised by Django because
                # the "ip" field because field is defined such that `null=True`
                pass

    def clean_fields(self, exclude=None) -> None:
        self._populate_subnet_and_vlan()
        super().clean_fields()

    @transactional
    def _populate_subnet_and_vlan(self) -> None:
        """
        The ReservedIP model allows to reserve an IP without providing a
        subnet or vlan. In such case, the model will look for the most suitable
        subnet and vlan and populate the model with them. If no subnet or vlan
        are found, a ValidationError is raised.

        The population of both fields only happens one even if the method is
        invoked several times.
        """
        ip = self.ip

        if not hasattr(self, "subnet"):
            if (subnet := Subnet.objects.get_best_subnet_for_ip(ip)) is None:
                raise ValidationError(
                    {
                        "subnet": "There is no suitable subnet for the IP provided."
                    }
                )
            else:
                self.subnet = subnet

        if not hasattr(self, "vlan"):
            self.vlan = self.subnet.vlan

    def __str__(self) -> str:
        self._populate_subnet_and_vlan()

        fields = [
            f"{self.ip} ({str(self.subnet.cidr)}, {str(self.vlan)})",
            self.mac_address,
            self.comment,
        ]
        return ", ".join(filter(None, fields))
