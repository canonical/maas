# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The IPRange handler for the WebSocket connection."""

from maasserver.forms.iprange import IPRangeForm
from maasserver.models import IPRange
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("websockets.iprange")


class IPRangeHandler(TimestampedModelHandler):
    class Meta:
        queryset = IPRange.objects.all().select_related("user", "subnet")
        pk = "id"
        form = IPRangeForm
        allowed_methods = ["list", "get", "create", "update", "delete"]
        listen_channels = ["iprange"]

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["vlan"] = None if obj.subnet is None else obj.subnet.vlan_id
        data["user"] = "" if obj.user is None else obj.user.username
        return data
