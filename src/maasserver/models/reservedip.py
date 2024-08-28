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
from maasserver.utils.orm import MAASQueriesMixin, transactional


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

        try:
            ip = ip_address(str(self.ip))
            if hasattr(self, "subnet"):
                net = ip_network(self.subnet.cidr)
                if ip not in ip_network(self.subnet.cidr):
                    raise ValidationError(
                        {"ip": "The provided IP is not part of the subnet."}
                    )
                if ip == net.network_address:
                    raise ValidationError(
                        {"ip": "The network address cannot be a reserved IP."}
                    )
                if ip == net.broadcast_address:
                    raise ValidationError(
                        {
                            "ip": "The broadcast address cannot be a reserved IP."
                        }
                    )
        except ValueError:
            # if self.ip is not valid IP address, a ValueError exception is
            # raised. The error is captured here to let the
            # GenericIPAddressField validator to raise a ValidationError.
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

        The population of both fields only happens the first time the method is
        used.
        """
        if self.mac_address == "":
            # Empty string changed to None to save this value as null in the
            # database. Otherwise, if undefined MAC addresses are stored as
            # empty strings (rather than as nulls) the uniqueness
            # vlan-mac_address avoids to create more than 1 reserved IP with
            # undefined MAC addresses in a VLAN.
            self.mac_address = None

        if ip := self.ip:
            if not hasattr(self, "subnet"):
                if (
                    subnet := Subnet.objects.get_best_subnet_for_ip(ip)
                ) is None:
                    raise ValidationError(
                        {
                            "subnet": "There is no suitable subnet for the IP provided."
                        }
                    )
                else:
                    self.subnet = subnet

            if not hasattr(self, "vlan"):
                self.vlan = self.subnet.vlan

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
