# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNSData form."""

__all__ = [
    "DNSDataForm",
]

from django import forms
from django.core.exceptions import ValidationError
from maasserver.forms import MAASModelForm
from maasserver.models.dnsdata import DNSData
from maasserver.models.dnsresource import DNSResource


class DNSDataForm(MAASModelForm):
    """DNSData creation/edition form."""

    dnsresource = forms.ModelChoiceField(
        label="DNS Resource",
        queryset=DNSResource.objects.all())
    ttl = forms.IntegerField(
        required=False, min_value=0, max_value=(1 << 31) - 1,
        label="Time To Live (seconds)",
        help_text="For how long is the answer valid?")
    rrtype = forms.CharField(
        label="Resource Type",
        help_text="Type of resource, if not an address")
    rrdata = forms.CharField(
        required=False, label="Resource Data",
        help_text="Resource Record data, if not an address")

    class Meta:
        model = DNSData
        fields = (
            'dnsresource',
            'ttl',
            'rrtype',
            'rrdata',
            )

    def clean(self):
        cleaned_data = super().clean()
        rrtype = self.data.get('rrtype', '')
        rrdata = self.data.get('rrdata', '')
        if rrtype != '' and rrdata == '' or rrtype == '' and rrdata != '':
            raise ValidationError(
                "Specify both rrtype and rrdata.")
        return cleaned_data
