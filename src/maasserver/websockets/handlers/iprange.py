# Copyright 2016-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The IPRange handler for the WebSocket connection."""

from maasserver.authorization import can_edit_global_entities
from maasserver.forms.iprange import IPRangeForm
from maasserver.models import IPRange
from maasserver.permissions import NodePermission
from maasserver.websockets.base import HandlerPermissionError
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
        view_permission = NodePermission.view

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["vlan"] = None if obj.subnet is None else obj.subnet.vlan_id
        data["user"] = "" if obj.user is None else obj.user.username
        return data

    def create(self, params):
        """Create an IP range."""
        if not can_edit_global_entities(self.user):
            raise HandlerPermissionError()
        return super().create(params)

    def update(self, params):
        """Update this IP range."""
        if not can_edit_global_entities(self.user):
            raise HandlerPermissionError()
        return super().update(params)

    def delete(self, params):
        """Delete this IP range."""
        if not can_edit_global_entities(self.user):
            raise HandlerPermissionError()
        return super().delete(params)
