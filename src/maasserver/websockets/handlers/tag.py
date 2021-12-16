# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.db.models import Count, Q

from maasserver.enum import NODE_TYPE
from maasserver.models.tag import Tag
from maasserver.websockets.base import AdminOnlyMixin
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class TagHandler(TimestampedModelHandler, AdminOnlyMixin):
    class Meta:
        queryset = Tag.objects.annotate(
            machine_count=Count(
                "node", filter=Q(node__node_type=NODE_TYPE.MACHINE)
            ),
            device_count=Count(
                "node", filter=Q(node__node_type=NODE_TYPE.DEVICE)
            ),
            controller_count=Count(
                "node",
                filter=Q(
                    node__node_type__in=(
                        NODE_TYPE.RACK_CONTROLLER,
                        NODE_TYPE.REGION_CONTROLLER,
                        NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                    )
                ),
            ),
        ).all()
        pk = "id"
        allowed_methods = [
            "list",
            "get",
            "create",
            "update",
            "delete",
        ]
        listen_channels = ["tag"]

    def _create(self, params):
        obj = super()._create(params)
        # add fields matching annotations from queryset to the object, since it
        # doesn't come from the DB
        for field in ("machine_count", "device_count", "controller_count"):
            setattr(obj, field, 0)
        return obj

    def dehydrate(self, obj, data, for_list=False):
        for field in ("machine_count", "device_count", "controller_count"):
            data[field] = getattr(obj, field)
        return data
