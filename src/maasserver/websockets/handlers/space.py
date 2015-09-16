# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The space handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "SpaceHandler",
    ]

from maasserver.models.space import Space
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class SpaceHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Space.objects.all().prefetch_related(
                "subnet_set__staticipaddress_set__interface_set"))
        pk = 'id'
        allowed_methods = ['list', 'get', 'set_active']
        listen_channels = [
            "space",
            ]

    def dehydrate(self, obj, data, for_list=False):
        data["subnet_ids"] = [
            subnet.id
            for subnet in obj.subnet_set.all()
        ]
        data["nodes_count"] = len({
            interface.node_id
            for subnet in obj.subnet_set.all()
            for ipaddress in subnet.staticipaddress_set.all()
            for interface in ipaddress.interface_set.all()
            if interface.node_id is not None
        })
        return data
