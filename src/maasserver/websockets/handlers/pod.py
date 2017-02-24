# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The node handler for the WebSocket connection."""

__all__ = [
    "PodHandler",
]

from maasserver.models.bmc import Pod
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.drivers.pod import Capabilities


class PodHandler(TimestampedModelHandler):

    class Meta:
        queryset = Pod.objects.all()
        pk = 'id'
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'delete',
        ]
        exclude = [
            'bmc_type',
            'cores',
            'local_disks',
            'local_storage',
            'memory',
            'power_parameters',
        ]

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["total"] = self.dehydrate_total(obj)
        data["used"] = self.dehydrate_used(obj)
        data["available"] = self.dehydrate_available(obj)
        return data

    def dehydrate_total(self, obj):
        """Dehydrate total Pod resources."""
        result = {
            'cores': obj.cores,
            'memory': obj.memory,
            'local_storage': obj.local_storage,
        }
        if Capabilities.FIXED_LOCAL_STORAGE in obj.capabilities:
            result['local_disks'] = obj.local_disks
        return result

    def dehydrate_used(self, obj):
        """Dehydrate used Pod resources."""
        result = {
            'cores': obj.get_used_cores(),
            'memory': obj.get_used_memory(),
            'local_storage': obj.get_used_local_storage(),
        }
        if Capabilities.FIXED_LOCAL_STORAGE in obj.capabilities:
            result['local_disks'] = obj.get_used_local_disks()
        return result

    def dehydrate_available(self, obj):
        """Dehydrate available Pod resources."""
        result = {}
        used = self.dehydrate_used(obj)
        for key, value in self.dehydrate_total(obj).items():
            result[key] = value - used[key]
        return result
