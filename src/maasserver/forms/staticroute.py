# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Static route form."""

from netaddr import IPAddress

from maasserver.fields import SpecifierOrModelChoiceField
from maasserver.forms import MAASModelForm
from maasserver.models.staticroute import StaticRoute
from maasserver.models.subnet import Subnet
from maasserver.utils.forms import set_form_error


class StaticRouteForm(MAASModelForm):
    """Static route creation/edition form."""

    source = SpecifierOrModelChoiceField(
        label="Source",
        queryset=Subnet.objects.all(),
        required=True,
        help_text="The source subnet for the route.",
    )

    destination = SpecifierOrModelChoiceField(
        label="Destination",
        queryset=Subnet.objects.all(),
        required=True,
        help_text="The destination subnet for the route.",
    )

    class Meta:
        model = StaticRoute
        fields = ("source", "destination", "gateway_ip", "metric")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Metric field is not a required field, but is required in the model.
        self.fields["metric"].required = False

    def clean(self):
        gateway_ip = self.cleaned_data.get("gateway_ip")
        source = self.cleaned_data.get("source")
        if gateway_ip:
            # This will not raise an AddrFormatErorr because it is validated at
            # the field first and if that fails the gateway_ip will be blank.
            if IPAddress(gateway_ip) not in source.get_ipnetwork():
                set_form_error(
                    self,
                    "gateway_ip",
                    "Enter an IP address in %s." % source.cidr,
                )

    def save(self):
        static_route = super().save(commit=False)
        if static_route.metric is None:
            # Set the initial value for the model.
            static_route.metric = 0
        static_route.save()
        return static_route
