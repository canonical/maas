# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The fabric handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "FabricHandler",
    ]

from maasserver.models.fabric import Fabric
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class FabricHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Fabric.objects.all().prefetch_related(
                "vlan_set__interface_set"))
        pk = 'id'
        allowed_methods = ['list', 'get', 'set_active']
        listen_channels = [
            "fabric",
            ]

    def dehydrate(self, obj, data, for_list=False):
        data["vlan_ids"] = [
            vlan.id
            for vlan in obj.vlan_set.all()
        ]
        data["nodes_count"] = len({
            interface.node_id
            for vlan in obj.vlan_set.all()
            for interface in vlan.interface_set.all()
            if interface.node_id is not None
        })
        return data
