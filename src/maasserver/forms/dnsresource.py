# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNSResource form."""

from collections.abc import Iterable

from django import forms
from netaddr import IPAddress
from netaddr.core import AddrFormatError

from maasserver.enum import IPADDRESS_TYPE
from maasserver.forms import APIEditMixin, MAASModelForm
from maasserver.models.dnsresource import (
    DNSResource,
    validate_dnsresource_name,
)
from maasserver.models.domain import Domain
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet


class DNSResourceForm(MAASModelForm):
    """DNSResource creation/edition form."""

    name = forms.CharField(label="Name")
    domain = forms.ModelChoiceField(
        label="Domain", queryset=Domain.objects.all()
    )
    address_ttl = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=(1 << 31) - 1,
        label="Time To Live (seconds)",
        help_text="For how long is the answer valid?",
    )
    ip_addresses = forms.CharField(
        required=False,
        label="IP Addresseses",
        help_text="The IP (or list of IPs), either as IDs or as addresses",
    )

    class Meta:
        model = DNSResource
        fields = ("name", "domain", "address_ttl", "ip_addresses")

    def __init__(
        self,
        data=None,
        instance=None,
        request=None,
        user=None,
        *args,
        **kwargs,
    ):
        # Always save the user, in case we create a StaticIPAddress in save().
        if request is not None:
            self.user = request.user
        if user is not None:
            self.user = user
        super().__init__(data=data, instance=instance, *args, **kwargs)  # noqa: B026

    def clean_ip(self, ipaddr):
        """Process one IP address (id or address) and return the id."""
        # If it's a simple number, then assume it's already an id.
        # If it's an IPAddress, then look up the id.
        # Otherwise, just return the input, which is likely to result in an
        # error later.
        if (
            isinstance(ipaddr, int)
            or isinstance(ipaddr, str)
            and ipaddr.isdigit()
        ):
            return int(ipaddr)
        elif isinstance(ipaddr, StaticIPAddress):
            # In Django 1.11, instead of getting an object ID, Django will
            # pre-adapt it to a StaticIPAddress.
            return ipaddr.id
        try:
            IPAddress(ipaddr)
        except (AddrFormatError, ValueError):
            # We have no idea, pass it on through and see what happens.
            return ipaddr
        ips = StaticIPAddress.objects.filter(ip=ipaddr)
        if ips.exists():
            return ips.first().id
        return ipaddr

    def clean(self):
        cleaned_data = super().clean()
        if self.data.get("ip_addresses", None) is not None:
            # we validate name here as well as in the model's save due
            # to the ip address relation not being written when an ip is first added
            validate_dnsresource_name(self.cleaned_data["name"], "A")
            ip_addresses = self.data.get("ip_addresses")
            if isinstance(ip_addresses, str):
                ip_addresses = ip_addresses.split()
            elif isinstance(ip_addresses, Iterable):
                ip_addresses = list(ip_addresses)
            else:
                ip_addresses = [ip_addresses]
            cleaned_data["ip_addresses"] = [
                self.clean_ip(ipaddr) for ipaddr in ip_addresses
            ]
        return cleaned_data

    def _post_clean(self):
        # address_ttl=None needs to make it through.  See also APIEditMixin
        self.cleaned_data = {
            key: value
            for key, value in self.cleaned_data.items()
            if value is not None or key == "address_ttl"
        }
        super(APIEditMixin, self)._post_clean()

    def save(self, *args, **kwargs):
        ip_addresses = self.cleaned_data.get("ip_addresses")
        new_list = []
        for ipaddr in ip_addresses:
            if isinstance(ipaddr, int):
                new_list.append(ipaddr)
                continue
            subnet = Subnet.objects.get_best_subnet_for_ip(ipaddr)
            static_ip, _ = StaticIPAddress.objects.get_or_create(
                ip="%s" % ipaddr,
                defaults={
                    "alloc_type": IPADDRESS_TYPE.USER_RESERVED,
                    "subnet": subnet,
                    "user": self.user,
                },
            )
            new_list.append(static_ip.id)
        self.cleaned_data["ip_addresses"] = new_list
        return super().save(*args, **kwargs)
