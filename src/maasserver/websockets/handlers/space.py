# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The space handler for the WebSocket connection."""

__all__ = [
    "SpaceHandler",
    ]

from maasserver.enum import NODE_PERMISSION
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
        allowed_methods = [
            'create',
            'delete',
            'get',
            'list',
            'set_active'
        ]
        listen_channels = [
            "space",
        ]

    def dehydrate(self, obj, data, for_list=False):
        data["name"] = obj.get_name()
        data["subnet_ids"] = [
            subnet.id
            for subnet in obj.subnet_set.all()
        ]
        return data

    def delete(self, parameters):
        """Delete this Space."""
        space = self.get_object(parameters)
        assert self.user.has_perm(
            NODE_PERMISSION.ADMIN, space), "Permission denied."
        space.delete()
