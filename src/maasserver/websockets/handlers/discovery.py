# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Discovery handler for the WebSocket connection."""

from datetime import datetime
import time

from maasserver.models import Discovery
from maasserver.permissions import NodePermission
from maasserver.websockets.base import (
    dehydrate_datetime,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.viewmodel import ViewModelHandler
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("websockets.discovery")


class DiscoveryHandler(ViewModelHandler):
    class Meta:
        queryset = Discovery.objects.by_unknown_ip_and_mac()
        batch_key = "first_seen"
        pk = "discovery_id"
        allowed_methods = ["list", "get", "clear", "delete_by_mac_and_ip"]

    def list(self, params):
        """List objects.

        :param start: A value of the `batch_key` column and NOT `pk`. They are
            often the same but that is not a certainty. Make sure the client
            also understands this distinction.
        :param offset: Offset into the queryset to return.
        :param limit: Maximum number of objects to return.
        """
        if "start" in params:
            params["start"] = datetime.fromtimestamp(float(params["start"]))
        return super().list(params)

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["mac_organization"] = obj.mac_organization
        return data

    def dehydrate_last_seen(self, obj):
        return dehydrate_datetime(obj)

    def dehydrate_first_seen(self, obj):
        # This is rendered all they way to microseconds so its always
        # unique. This is because each discovery item is always created in
        # is own transaction. If this changes then the barch key needs to
        # be changed to something that is ordered and unique.
        return str(time.mktime(obj.timetuple()) + obj.microsecond / 1e6)

    def clear(self, params=None):
        if params is None:
            params = dict()
        if not self.user.has_perm(NodePermission.admin, Discovery):
            raise HandlerPermissionError()
        if len(params) == 0:
            params["all"] = True
        Discovery.objects.clear(**params)

    def delete_by_mac_and_ip(self, params=None):
        if params is None:
            params = dict()
        if not self.user.has_perm(NodePermission.admin, Discovery):
            raise HandlerPermissionError()
        ip = params.get("ip", None)
        if ip is None:
            raise ValueError("IP address required.")
        mac = params.get("mac", None)
        if mac is None:
            raise ValueError("MAC address required.")
        delete_result = Discovery.objects.delete_by_mac_and_ip(ip=ip, mac=mac)
        # Return the count of objects deleted.
        return delete_result[0]
