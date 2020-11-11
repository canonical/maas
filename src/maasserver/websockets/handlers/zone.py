# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The zone handler for the WebSocket connection."""


from collections import defaultdict

from django.db.models import Count

from maasserver.enum import NODE_TYPE
from maasserver.forms import ZoneForm
from maasserver.models.zone import Zone
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class ZoneHandler(TimestampedModelHandler):
    class Meta:
        queryset = Zone.objects.all().prefetch_related("node_set")
        pk = "id"
        form = ZoneForm
        form_requires_request = False
        allowed_methods = [
            "create",
            "update",
            "delete",
            "get",
            "list",
            "set_active",
        ]
        listen_channels = ["zone"]

    def delete(self, parameters):
        """Delete this Zone."""
        zone = self.get_object(parameters)
        assert self.user.is_superuser, "Permission denied."
        zone.delete()

    def dehydrate(self, zone, data, for_list=False):
        node_count_by_type = defaultdict(
            int,
            zone.node_set.values("node_type")
            .annotate(node_count=Count("node_type"))
            .values_list("node_type", "node_count"),
        )
        data.update(
            {
                "devices_count": node_count_by_type[NODE_TYPE.DEVICE],
                "machines_count": node_count_by_type[NODE_TYPE.MACHINE],
                "controllers_count": (
                    node_count_by_type[NODE_TYPE.RACK_CONTROLLER]
                    + node_count_by_type[NODE_TYPE.REGION_CONTROLLER]
                    + node_count_by_type[NODE_TYPE.REGION_AND_RACK_CONTROLLER]
                ),
            }
        )
        return data
