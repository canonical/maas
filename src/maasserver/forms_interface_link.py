# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Interface link form."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "InterfaceLinkForm",
]

from django import forms
from maasserver.enum import (
    INTERFACE_LINK_TYPE,
    INTERFACE_LINK_TYPE_CHOICES,
    IPADDRESS_TYPE,
)
from maasserver.fields import CaseInsensitiveChoiceField
from maasserver.models.interface import Interface
from maasserver.utils.forms import (
    compose_invalid_choice_text,
    set_form_error,
)
from maasserver.utils.orm import get_one
from netaddr import IPAddress


class InterfaceLinkForm(forms.Form):
    """Interface link form."""

    mode = CaseInsensitiveChoiceField(
        choices=INTERFACE_LINK_TYPE_CHOICES, required=True,
        error_messages={
            'invalid_choice': compose_invalid_choice_text(
                'mode', INTERFACE_LINK_TYPE_CHOICES),
        })

    subnet = forms.ModelChoiceField(queryset=None, required=False)

    ip_address = forms.GenericIPAddressField(required=False)

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance")
        super(InterfaceLinkForm, self).__init__(*args, **kwargs)
        self.fields['subnet'].queryset = self.instance.vlan.subnet_set.all()

    def clean(self):
        cleaned_data = super(InterfaceLinkForm, self).clean()
        mode = cleaned_data.get("mode", None)
        if mode == INTERFACE_LINK_TYPE.DHCP:
            self._clean_mode_dhcp()
        elif mode == INTERFACE_LINK_TYPE.STATIC:
            self._clean_mode_static(cleaned_data)
        elif mode == INTERFACE_LINK_TYPE.LINK_UP:
            self._clean_mode_link_up()
        return cleaned_data

    def _clean_mode_dhcp(self):
        # Can only have one DHCP link on an interface.
        dhcp_address = get_one(
            self.instance.ip_addresses.filter(
                alloc_type=IPADDRESS_TYPE.DHCP))
        if dhcp_address is not None:
            if dhcp_address.subnet is not None:
                set_form_error(
                    self, "mode",
                    "Interface is already set to DHCP from '%s'." % (
                        dhcp_address.subnet))
            else:
                set_form_error(
                    self, "mode", "Interface is already set to DHCP.")

    def _clean_mode_static(self, cleaned_data):
        subnet = cleaned_data.get("subnet", None)
        ip_address = cleaned_data.get("ip_address", None)
        if subnet is None:
            set_form_error(self, "subnet", "This field is required.")
        elif ip_address:
            ip_address = IPAddress(ip_address)
            if ip_address not in subnet.get_ipnetwork():
                set_form_error(
                    self, "ip_address",
                    "IP address is not in the given subnet '%s'." % subnet)
            ngi = subnet.get_managed_cluster_interface()
            if (ngi is not None and
                    ip_address in ngi.get_dynamic_ip_range()):
                set_form_error(
                    self, "ip_address",
                    "IP address is inside a managed dynamic range "
                    "%s to %s." % (ngi.ip_range_low, ngi.ip_range_high))

    def _clean_mode_link_up(self):
        # Cannot set LINK_UP unless no other IP address are attached to
        # this interface.
        if self.instance.ip_addresses.count() > 0:
            set_form_error(
                self, "mode",
                "Cannot configure interface to link up (with no IP address)"
                "while other links are already configured.")

    def save(self):
        mode = self.cleaned_data.get("mode", None)
        subnet = self.cleaned_data.get("subnet", None)
        ip_address = self.cleaned_data.get("ip_address", None)
        if not ip_address:
            ip_address = None
        self.instance.link_subnet(mode, subnet, ip_address=ip_address)
        return Interface.objects.get(id=self.instance.id)


class InterfaceUnlinkForm(forms.Form):
    """Interface unlink form."""

    id = forms.ChoiceField(
        choices=INTERFACE_LINK_TYPE_CHOICES, required=True,
        error_messages={
            'invalid_choice': compose_invalid_choice_text(
                'mode', INTERFACE_LINK_TYPE_CHOICES),
        })

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop("instance")
        super(InterfaceUnlinkForm, self).__init__(*args, **kwargs)
        self.set_up_id_field()

    def set_up_id_field(self):
        link_ids = self.instance.ip_addresses.all().values_list(
            "id", flat=True)
        link_choices = [
            (link_id, link_id)
            for link_id in link_ids
        ]
        invalid_choice = compose_invalid_choice_text('id', link_choices)
        self.fields["id"] = forms.ChoiceField(
            choices=link_choices, required=True,
            error_messages={
                'invalid_choice': invalid_choice,
            })

    def save(self):
        link_id = self.cleaned_data.get("id", None)
        self.instance.unlink_subnet_by_id(link_id)
        return Interface.objects.get(id=self.instance.id)
