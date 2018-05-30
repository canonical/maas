# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The resource pool handler for the WebSocket connection."""

__all__ = [
    "ResourcePoolHandler",
    ]

from django.db.models import (
    Case,
    Count,
    IntegerField,
    Sum,
    When,
)
from maasserver.enum import NODE_STATUS
from maasserver.forms import ResourcePoolForm
from maasserver.models.resourcepool import ResourcePool
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class ResourcePoolHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            ResourcePool.objects.all().prefetch_related(
                'node_set').annotate(
                    machine_total_count=Count('node'),
                    machine_ready_count=Sum(
                        Case(
                            When(node__status=NODE_STATUS.READY, then=1),
                            default=0, output_field=IntegerField()))))

        pk = 'id'
        form = ResourcePoolForm
        form_requires_request = False
        allowed_methods = [
            'create',
            'update',
            'delete',
            'get',
            'list',
        ]
        listen_channels = [
            "resourcepool",
        ]

    def delete(self, parameters):
        """Delete this resource pool."""
        pool = self.get_object(parameters)
        assert self.user.is_superuser, "Permission denied."
        pool.delete()

    def dehydrate(self, obj, data, for_list=False):
        """Add any extra info to the `data` before finalizing the final object.

        :param obj: object being dehydrated.
        :param data: dictionary to place extra info.
        :param for_list: True when the object is being converted to belong
            in a list.
        """
        for attr in ['machine_total_count', 'machine_ready_count']:
            data[attr] = getattr(obj, attr)
        data['is_default'] = obj.is_default()
        return data
