# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Domain form."""


from django import forms
from django.core.exceptions import ValidationError

from maasserver.fields import IPListFormField
from maasserver.forms import APIEditMixin, MAASModelForm
from maasserver.models.domain import Domain
from maasserver.models.forwarddnsserver import ForwardDNSServer


class DomainForm(MAASModelForm):
    """Domain creation/edition form."""

    class Meta:
        model = Domain
        fields = ("name", "authoritative", "ttl")

    ttl = forms.IntegerField(min_value=1, max_value=604800, required=False)

    authoritative = forms.NullBooleanField(required=False)

    forward_dns_servers = IPListFormField(required=False)

    def save(self):
        super(MAASModelForm, self).save()
        fwd_srvrs = self.cleaned_data.get("forward_dns_servers")
        if fwd_srvrs is not None:
            fwd_srvrs_list = fwd_srvrs.split(" ")
            for fwd_srvr_ip in fwd_srvrs_list:
                fwd_srvr = ForwardDNSServer.objects.get_or_create(
                    ip_address=fwd_srvr_ip
                )[0]
                fwd_srvr.domains.add(self.instance)
                fwd_srvr.save()
            del self.cleaned_data["forward_dns_servers"]
        return self.instance

    def clean(self):
        if self.data.get("authoritative") and len(
            self.data.get("forward_dns_servers", "")
        ):
            raise ValidationError(
                "a domain cannot be both authoritative and have forward dns servers"
            )
        super().clean()

    def _post_clean(self):
        # ttl=None needs to make it through.  See also APIEditMixin
        self.cleaned_data = {
            key: value
            for key, value in self.cleaned_data.items()
            if value is not None or key == "ttl"
        }
        super(APIEditMixin, self)._post_clean()
