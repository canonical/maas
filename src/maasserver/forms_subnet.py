# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Subnet form."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "SubnetForm",
]

from django import forms
from maasserver.fields import IPListFormField
from maasserver.forms import MAASModelForm
from maasserver.models.fabric import Fabric
from maasserver.models.space import Space
from maasserver.models.subnet import Subnet
from maasserver.models.vlan import VLAN
from maasserver.utils.forms import set_form_error
from maasserver.utils.orm import get_one


class SubnetForm(MAASModelForm):
    """Subnet creation/edition form."""

    fabric = forms.ModelChoiceField(
        queryset=Fabric.objects.all(), required=False)

    vlan = forms.ModelChoiceField(
        queryset=VLAN.objects.all(), required=False)

    vid = forms.IntegerField(
        min_value=0, max_value=4095, required=False)

    space = forms.ModelChoiceField(
        queryset=Space.objects.all(), required=False)

    class Meta:
        model = Subnet
        fields = (
            'name',
            'vlan',
            'space',
            'cidr',
            'gateway_ip',
            'dns_servers',
            )

    def __init__(self, *args, **kwargs):
        super(SubnetForm, self).__init__(*args, **kwargs)
        self.fields['name'].required = False

    def clean(self):
        cleaned_data = super(SubnetForm, self).clean()
        # The djorm_pgarray.fields.ArrayField form has a bug which leaves out
        # the first entry.
        if 'dns_servers' in self.data and self.data['dns_servers'] != '':
            cleaned_data['dns_servers'] = self.data.getlist('dns_servers')
        cleaned_data = self._clean_name(cleaned_data)
        cleaned_data = self._clean_dns_servers(cleaned_data)
        if self.instance.id is None:
            # We only allow the helpers when creating. When updating we require
            # the VLAN specifically. This is because we cannot make a correct
            # determination on what should be done in this case.
            cleaned_data = self._clean_vlan(cleaned_data)
            cleaned_data = self._clean_space(cleaned_data)
        return cleaned_data

    def _clean_name(self, cleaned_data):
        name = cleaned_data.get("name", None)
        instance_name_and_cidr_match = (
            self.instance.id is not None and
            name == self.instance.name and
            name == self.instance.cidr)
        if (not name and "cidr" not in self.errors and
                self.instance.id is None):
            # New subnet without name so set it to cidr.
            cleaned_data["name"] = cleaned_data["cidr"]
        elif instance_name_and_cidr_match and "cidr" not in self.errors:
            # Update the subnet to have the same name as its cidr.
            cleaned_data["name"] = cleaned_data["cidr"]
        return cleaned_data

    def _clean_vlan(self, cleaned_data):
        fabric = cleaned_data.get("fabric", None)
        vlan = cleaned_data.get("vlan", None)
        vid = cleaned_data.get("vid", None)
        if fabric is None and vlan is None:
            if not vid:
                cleaned_data["vlan"] = (
                    Fabric.objects.get_default_fabric().get_default_vlan())
            else:
                vlan = get_one(
                    VLAN.objects.filter(
                        fabric=Fabric.objects.get_default_fabric(), vid=vid))
                if vlan is None:
                    set_form_error(
                        self, "vid",
                        "No VLAN with vid %s in default fabric." % vid)
                else:
                    cleaned_data["vlan"] = vlan
        elif fabric is not None:
            if vlan is None:
                if not vid:
                    cleaned_data["vlan"] = fabric.get_default_vlan()
                else:
                    vlan = get_one(VLAN.objects.filter(fabric=fabric, vid=vid))
                    if vlan is None:
                        set_form_error(
                            self, "vid",
                            "No VLAN with vid %s in fabric %s." % (
                                vid, fabric))
                    else:
                        cleaned_data["vlan"] = vlan
            elif vlan.fabric_id != fabric.id:
                set_form_error(
                    self, "vlan",
                    "VLAN %s is not in fabric %s." % (vlan, fabric))
        return cleaned_data

    def _clean_space(self, cleaned_data):
        space = cleaned_data.get("space", None)
        if space is None:
            cleaned_data["space"] = Space.objects.get_default_space()
        return cleaned_data

    def _clean_dns_servers(self, cleaned_data):
        dns_servers = cleaned_data.get("dns_servers", None)
        if dns_servers is None:
            return cleaned_data
        clean_dns_servers = []
        for dns_server in dns_servers:
            ip_list_form = IPListFormField()
            ip_list_cleaned = ip_list_form.clean(dns_server)
            clean_dns_servers += ip_list_cleaned.split(" ")
        cleaned_data["dns_servers"] = clean_dns_servers
        return cleaned_data
