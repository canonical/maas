# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNSData form."""

from django import forms

from maasserver.forms import APIEditMixin, MAASModelForm
from maasserver.models.dnsdata import DNSData
from maasserver.models.dnsresource import DNSResource


class DNSDataForm(MAASModelForm):
    """DNSData creation/edition form."""

    dnsresource = forms.ModelChoiceField(
        label="DNS Resource", queryset=DNSResource.objects.all()
    )
    ttl = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=(1 << 31) - 1,
        label="Time To Live (seconds)",
        help_text="For how long is the answer valid?",
    )
    rrtype = forms.CharField(
        label="Resource Type", help_text="Type of resource, if not an address"
    )
    rrdata = forms.CharField(
        label="Resource Data",
        help_text="Resource Record data, if not an address",
    )

    class Meta:
        model = DNSData
        fields = ("dnsresource", "ttl", "rrtype", "rrdata")

    def _post_clean(self):
        # ttl=None needs to make it through.  See also APIEditMixin
        self.cleaned_data = {
            key: value
            for key, value in self.cleaned_data.items()
            if value is not None or key == "ttl"
        }
        super(APIEditMixin, self)._post_clean()
