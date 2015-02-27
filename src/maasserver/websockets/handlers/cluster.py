# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The cluster handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ClusterHandler",
    ]

from maasserver.clusterrpc.power_parameters import (
    get_all_power_types_from_clusters,
    )
from maasserver.models.nodegroup import NodeGroup
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
    )


class ClusterHandler(TimestampedModelHandler):

    class Meta:
        queryset = NodeGroup.objects.all()
        pk = 'id'
        allowed_methods = ['list', 'get']
        exclude = [
            "api_token",
            "api_key",
            "dhcp_key",
            "maas_url",
            ]
        listen_channels = [
            "nodegroup",
            ]

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["connected"] = obj.is_connected()
        data["state"] = obj.get_state()
        data["power_types"] = self.dehydrate_power_types(obj)
        return data

    def dehydrate_power_types(self, obj):
        """Return all the power types."""
        return get_all_power_types_from_clusters(nodegroups=[obj])
