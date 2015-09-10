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
from maasserver.forms import MAASModelForm
from maasserver.models.space import Space
from maasserver.models.subnet import Subnet
from maasserver.models.vlan import VLAN


class SubnetForm(MAASModelForm):
    """Subnet creation/edition form."""

    vlan = forms.ModelChoiceField(
        queryset=VLAN.objects.all(), required=True)

    space = forms.ModelChoiceField(
        queryset=Space.objects.all(), required=True)

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
