# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Reserved IP handler for the WebSocket connection"""

from django.db.models.query import QuerySet

from maasserver.forms.reservedip import ReservedIPForm
from maasserver.models.reservedip import ReservedIP
from maasserver.websockets.base import HandlerValidationError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class ReservedIPHandler(TimestampedModelHandler):

    class Meta:
        queryset: QuerySet = ReservedIP.objects.all().select_related("subnet")
        pk: str = "id"
        form: ReservedIPForm = ReservedIPForm
        allowed_methods: list[str] = [
            "create",
            "update",
            "delete",
            "get",
            "list",
        ]

    def update(self, params: dict):
        entry_id = params.get("id", None)
        ip = params.get("ip", None)
        subnet_id = params.get("subnet", None)
        vlan_id = params.get("vlan", None)

        if entry_id is None:
            raise HandlerValidationError({"id": "Missing value."})

        if ip and (ip != self.get({"id": entry_id})["ip"]):
            # IP is associated to the Reserved IP entry, and it cannot be changed.
            raise HandlerValidationError({"ip": "Field cannot be changed."})

        if (
            subnet_id
            and subnet_id
            != ReservedIP.objects.filter(id=entry_id)[0].subnet.id
        ):
            # Subnet is linked to the IP, i.e. it cannot be changed.
            raise HandlerValidationError(
                {"subnet": "Field cannot be changed."}
            )

        if (
            vlan_id
            and vlan_id != ReservedIP.objects.filter(id=entry_id)[0].vlan.id
        ):
            # VLAN, as subnet, is linked to the IP, i.e. it cannot be changed.
            raise HandlerValidationError({"vlan": "Field cannot be changed."})

        return super().update(params)
