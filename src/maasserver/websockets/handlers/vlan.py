# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The vlan handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "VLANHandler",
    ]

from maasserver.models.vlan import VLAN
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class VLANHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            VLAN.objects.all()
                .prefetch_related("interface_set")
                .prefetch_related("subnet_set"))
        pk = 'id'
        allowed_methods = ['list', 'get', 'set_active']
        listen_channels = [
            "vlan",
            ]

    def dehydrate(self, obj, data, for_list=False):
        data["subnet_ids"] = [
            subnet.id
            for subnet in obj.subnet_set.all()
        ]
        data["nodes_count"] = len({
            interface.node_id
            for interface in obj.interface_set.all()
            if interface.node_id is not None
        })
        return data
