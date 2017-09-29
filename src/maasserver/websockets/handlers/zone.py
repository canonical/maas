# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The zone handler for the WebSocket connection."""

__all__ = [
    "ZoneHandler",
    ]

from maasserver.enum import NODE_TYPE
from maasserver.forms import ZoneForm
from maasserver.models.zone import Zone
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class ZoneHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Zone.objects.all()
            .prefetch_related('node_set'))
        pk = 'id'
        form = ZoneForm
        form_requires_request = False
        allowed_methods = [
            'create',
            'update',
            'delete',
            'get',
            'list',
            'set_active',
        ]
        listen_channels = [
            "zone",
            ]

    def delete(self, parameters):
        """Delete this Zone."""
        zone = self.get_object(parameters)
        assert self.user.is_superuser, "Permission denied."
        zone.delete()

    def dehydrate(self, zone, data, for_list=False):
        data['devices_count'] = len([
            node
            for node in zone.node_set.all()
            if node.node_type == NODE_TYPE.DEVICE
        ])
        data['machines_count'] = len([
            node
            for node in zone.node_set.all()
            if node.node_type == NODE_TYPE.MACHINE
        ])
        data['controllers_count'] = len([
            node
            for node in zone.node_set.all()
            if (
                node.node_type == NODE_TYPE.RACK_CONTROLLER or
                node.node_type == NODE_TYPE.REGION_CONTROLLER or
                node.node_type == NODE_TYPE.REGION_AND_RACK_CONTROLLER)
        ])
        return data
