# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Reserved IP form."""

from django.core.handlers.wsgi import WSGIRequest

from maasserver.forms import MAASModelForm
from maasserver.models import ReservedIP
from maasserver.models.subnet import Subnet


class ReservedIPForm(MAASModelForm):
    """ReservedIp creation/edition form."""

    class Meta:
        model = ReservedIP
        fields = ("ip", "subnet", "vlan", "mac_address", "comment")

    def __init__(
        self,
        data: dict | None = None,
        instance: ReservedIP | None = None,
        request: WSGIRequest | None = None,
        *args,
        **kwargs,
    ):
        data = {} if data is None else data.copy()

        if instance is None:
            ip = data.get("ip")
            subnet_id = data.get("subnet")
            vlan_id = data.get("vlan")

            if subnet_id is None and ip is not None:
                subnet = Subnet.objects.get_best_subnet_for_ip(ip)
                subnet_id = subnet.id if subnet else None
                data["subnet"] = subnet_id

            if vlan_id is None and subnet_id is not None:
                if subnet := Subnet.objects.filter(id=subnet_id):
                    data["vlan"] = subnet[0].vlan.id

        super().__init__(data=data, instance=instance, *args, **kwargs)
