# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fan Network form."""


from maasserver.forms import MAASModelForm
from maasserver.models.fannetwork import FanNetwork


class FanNetworkForm(MAASModelForm):
    """Fan Network creation/edition form."""

    class Meta:
        model = FanNetwork
        fields = (
            "name",
            "underlay",
            "overlay",
            "dhcp",
            "host_reserve",
            "bridge",
            "off",
        )
