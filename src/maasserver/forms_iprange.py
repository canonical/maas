# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""IPRange form."""
from maasserver.models import Subnet


__all__ = [
    "IPRangeForm",
]

from maasserver.forms import MAASModelForm
from maasserver.models.iprange import IPRange


class IPRangeForm(MAASModelForm):
    """IPRange creation/edition form."""

    class Meta:
        model = IPRange
        fields = (
            'subnet',
            'type',
            'start_ip',
            'end_ip',
            'user',
            'comment',
            )

    def __init__(
            self, data=None, instance=None, request=None, *args, **kwargs):
        if data is None:
            data = {}
        # If this is a new IPRange, fill in the 'user' and 'subnet' fields
        # automatically, if necessary.
        if instance is None:
            start_ip = data.get('start_ip')
            subnet = data.get('subnet')
            user = data.get('subnet')
            if subnet is None and start_ip is not None:
                subnet = Subnet.objects.get_best_subnet_for_ip(start_ip)
                if subnet is not None:
                    data['subnet'] = subnet.id
            if user is None and request is not None:
                data['user'] = request.user.id
        super().__init__(
            data=data, instance=instance, *args, **kwargs)
