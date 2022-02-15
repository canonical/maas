# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Script handler for the WebSocket connection."""

from operator import attrgetter

from maasserver.models import NodeDevice
from maasserver.websockets.base import HandlerPKError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class NodeDeviceHandler(TimestampedModelHandler):
    class Meta:
        queryset = NodeDevice.objects.all()
        pk = "id"
        allowed_methods = ["list", "delete"]
        listen_channels = ["nodedevice"]

    def dehydrate(self, obj, data, for_list=False):
        # When NodeDevices are loaded in the UI the client has already received
        # the keys below. Instead of reprocessing them make it clear the handler
        # is only returning the ids, not values.
        for key in [
            "physical_blockdevice",
            "physical_interface",
            "numa_node",
            "node_config",
        ]:
            id = data.pop(key)
            data[f"{key}_id"] = id

        data["node_id"] = obj.node_config.node_id
        return data

    def list(self, params):
        """List NodeDevice objects.

        :param system_id: `Node.system_id` for the NodeDevices.
        """
        if "system_id" not in params:
            raise HandlerPKError("Missing system_id in params")
        system_id = params["system_id"]

        qs = self.get_queryset(for_list=True)
        qs = qs.filter(node_config__node__system_id=system_id)

        objs = list(qs)
        getpk = attrgetter(self._meta.pk)
        self.cache["loaded_pks"].update(getpk(obj) for obj in objs)
        return [self.full_dehydrate(obj, for_list=True) for obj in objs]
