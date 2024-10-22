# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Reserved IP handler for the WebSocket connection"""

from django.db.models.query import QuerySet

from maasserver.dhcp import configure_dhcp_on_agents
from maasserver.forms.reservedip import ReservedIPForm
from maasserver.models import Interface
from maasserver.models.reservedip import ReservedIP
from maasserver.utils.orm import post_commit_do
from maasserver.websockets.base import HandlerValidationError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class ReservedIPHandler(TimestampedModelHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._node_summary_cache = {}

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

    def _load_extra_data_before_dehydrate(self, objs, for_list=False):
        # We want to fetch all the nodes related to the reserved ips in just one shot.
        if for_list:
            objs = list(objs)
            interfaces = Interface.objects.prefetch_related(
                "node_config__node", "node_config__node__domain"
            ).filter(mac_address__in=[x.mac_address for x in objs])
            self._node_summary_cache = {}
            for interface in interfaces:
                node = interface.get_node()
                self._node_summary_cache[interface.mac_address] = {
                    "fqdn": node.fqdn,
                    "hostname": node.hostname,
                    "node_type": node.node_type,
                    "system_id": node.system_id,
                    "via": interface.name,
                }

    def dehydrate(self, obj, data: dict, for_list: bool = False) -> dict:
        if for_list:
            # Use None if the reserved ip is not linked to any known interface/node.
            data["node_summary"] = self._node_summary_cache.get(
                data["mac_address"], None
            )
        return data

    def create(self, params: dict) -> dict:
        reserved_ip = super().create(params)
        post_commit_do(
            configure_dhcp_on_agents, reserved_ip_ids=[reserved_ip["id"]]
        )
        return reserved_ip

    def update(self, params: dict):
        entry_id = params.get("id", None)

        if entry_id is None:
            raise HandlerValidationError({"id": "Missing value."})

        updated_reserved_ip = super().update(params)
        # No need to trigger an update because it's not possible to change the ip or the mac address of a reserved ip.

        return updated_reserved_ip

    def delete(self, params: dict) -> None:
        reserved_ip = self.get_object(params)
        post_commit_do(
            configure_dhcp_on_agents, subnet_ids=[reserved_ip.subnet.id]
        )
        reserved_ip.delete()
