# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Reserved IP form."""
from ipaddress import ip_address, ip_network

from django import forms
from django.core.exceptions import ValidationError

from maasserver.fields import MACAddressFormField, SpecifierOrModelChoiceField
from maasserver.forms import MAASModelForm
from maasserver.models import ReservedIP, StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.utils.forms import set_form_error


class ReservedIPForm(MAASModelForm):
    """ReservedIp creation/edition form."""

    ip = forms.GenericIPAddressField(required=True)

    mac_address = MACAddressFormField(required=True)

    subnet = SpecifierOrModelChoiceField(
        queryset=Subnet.objects.all(), required=False, empty_label=""
    )

    comment = forms.CharField(required=False)

    class Meta:
        model = ReservedIP
        fields = ("ip", "subnet", "mac_address", "comment")

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        if self.instance and self.instance.id:
            if (
                self.data["ip"] != self.instance.ip
                or self.data["mac_address"] != self.instance.mac_address
                or self.data["subnet"] != self.instance.subnet.id
            ):
                raise ValidationError(
                    "The ip, mac_address and the subnet of a reserved ip are immutable. Please delete the entry and recreate it."
                )

        cleaned_data = super().clean()
        ip = cleaned_data.get("ip", None)
        subnet = cleaned_data.get("subnet", None)
        if (
            ip
            and subnet
            and (dynamic_range := subnet.get_dynamic_range_for_ip(ip))
        ):
            set_form_error(
                self,
                "ip",
                f"The ip {ip} must be outside the dynamic range {dynamic_range.start_ip} - {dynamic_range.end_ip}.",
            )
        return cleaned_data

    def clean_subnet(self):
        subnet = self.cleaned_data.get("subnet", None)
        ip = self.cleaned_data.get("ip", None)
        if ip is None:
            # ip is required, django will do the job for us and return an error.
            return
        if subnet is None:
            subnet = Subnet.objects.get_best_subnet_for_ip(ip)
            if not subnet:
                raise ValidationError(
                    f"Could not find a sutable subnet for {ip}. Please create the subnet first."
                )

        subnet_network = ip_network(subnet.cidr)
        if ip_address(ip) not in subnet_network:
            set_form_error(
                self,
                "ip",
                "The provided IP is not part of the subnet.",
            )
        if ip_address(ip) == subnet_network.network_address:
            set_form_error(
                self,
                "ip",
                "The network address cannot be a reserved IP.",
            )

        if ip_address(ip) == subnet_network.broadcast_address:
            set_form_error(
                self,
                "ip",
                "The broadcast address cannot be a reserved IP.",
            )

        return subnet

    def clean_ip(self):
        ip = self.data.get("ip")
        mac_address = self.data.get("mac_address")
        existing_ip = StaticIPAddress.objects.filter(ip=ip).first()
        if existing_ip and mac_address not in existing_ip.get_mac_addresses():
            set_form_error(
                self,
                "ip",
                f"The ip {ip} is already in use by another machine.",
            )
        return ip
