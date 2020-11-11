# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""IPRange form."""


from django import forms
from django.contrib.auth.models import User

from maasserver.forms import MAASModelForm
from maasserver.models import Subnet
from maasserver.models.iprange import IPRange


class IPRangeForm(MAASModelForm):
    """IPRange creation/edition form."""

    user = forms.ModelChoiceField(
        required=False, queryset=User.objects, to_field_name="username"
    )

    class Meta:
        model = IPRange
        fields = ("subnet", "type", "start_ip", "end_ip", "user", "comment")

    def __init__(
        self, data=None, instance=None, request=None, *args, **kwargs
    ):
        if data is None:
            data = {}
        else:
            data = data.copy()
        # If this is a new IPRange, fill in the 'user' and 'subnet' fields
        # automatically, if necessary.
        if instance is None:
            start_ip = data.get("start_ip")
            subnet = data.get("subnet")
            if subnet is None and start_ip is not None:
                subnet = Subnet.objects.get_best_subnet_for_ip(start_ip)
                if subnet is not None:
                    data["subnet"] = subnet.id
            if request is not None:
                data["user"] = request.user.username
        elif instance.user and "user" not in data:
            data["user"] = instance.user.username
        super().__init__(data=data, instance=instance, *args, **kwargs)
