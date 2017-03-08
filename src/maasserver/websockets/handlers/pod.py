# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The node handler for the WebSocket connection."""

__all__ = [
    "PodHandler",
]

from functools import partial

from django.http import HttpRequest
from maasserver.enum import NODE_TYPE
from maasserver.forms.pods import PodForm
from maasserver.models.bmc import Pod
from maasserver.utils.orm import (
    reload_object,
    transactional,
)
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import HandlerValidationError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.drivers.pod import Capabilities
from provisioningserver.utils.twisted import asynchronous


class PodHandler(TimestampedModelHandler):

    class Meta:
        queryset = Pod.objects.all()
        pk = 'id'
        form = PodForm
        form_requires_request = True
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'delete',
            'refresh',
        ]
        exclude = [
            'bmc_type',
            'cores',
            'local_disks',
            'local_storage',
            'memory',
            'power_parameters'
        ]

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        if reload_object(self.user).is_superuser:
            data['power_parameters'] = obj.power_parameters
        data["total"] = self.dehydrate_total(obj)
        data["used"] = self.dehydrate_used(obj)
        data["available"] = self.dehydrate_available(obj)
        data["composed_machines_count"] = obj.node_set.filter(
            node_type=NODE_TYPE.MACHINE).count()
        return data

    def dehydrate_total(self, obj):
        """Dehydrate total Pod resources."""
        result = {
            'cores': obj.cores,
            'memory': obj.memory,
            'memory_gb': '%.1f' % (obj.memory / 1024.0),
            'local_storage': obj.local_storage,
            'local_storage_gb': '%.1f' % (obj.local_storage / (1024 ** 3)),
        }
        if Capabilities.FIXED_LOCAL_STORAGE in obj.capabilities:
            result['local_disks'] = obj.local_disks
        return result

    def dehydrate_used(self, obj):
        """Dehydrate used Pod resources."""
        used_memory = obj.get_used_memory()
        used_local_storage = obj.get_used_local_storage()
        result = {
            'cores': obj.get_used_cores(),
            'memory': used_memory,
            'memory_gb': '%.1f' % (used_memory / 1024.0),
            'local_storage': used_local_storage,
            'local_storage_gb': '%.1f' % (used_local_storage / (1024 ** 3)),
        }
        if Capabilities.FIXED_LOCAL_STORAGE in obj.capabilities:
            result['local_disks'] = obj.get_used_local_disks()
        return result

    def dehydrate_available(self, obj):
        """Dehydrate available Pod resources."""
        used_memory = obj.get_used_memory()
        used_local_storage = obj.get_used_local_storage()
        result = {
            'cores': obj.cores - obj.get_used_cores(),
            'memory': obj.memory - used_memory,
            'memory_gb': '%.1f' % ((obj.memory - used_memory) / 1024.0),
            'local_storage': obj.local_storage - used_local_storage,
            'local_storage_gb': '%.1f' % (
                (obj.local_storage - used_local_storage) / (1024 ** 3)),
        }
        if Capabilities.FIXED_LOCAL_STORAGE in obj.capabilities:
            result['local_disks'] = (
                obj.local_disks - obj.get_used_local_disks())
        return result

    @asynchronous
    def create(self, params):
        """Create a pod."""
        assert self.user.is_superuser, "Permission denied."

        @transactional
        def get_form(params):
            request = HttpRequest()
            request.user = self.user
            form = PodForm(data=params, request=request)
            if not form.is_valid():
                raise HandlerValidationError(form.errors)
            else:
                return form

        @transactional
        def render_obj(obj):
            return self.full_dehydrate(obj)

        d = deferToDatabase(get_form, params)
        d.addCallback(lambda form: form.save())
        d.addCallback(partial(deferToDatabase, render_obj))
        return d

    @asynchronous
    def delete(self, params):
        """Delete the object."""
        assert self.user.is_superuser, "Permission denied."

        d = deferToDatabase(transactional(self.get_object), params)
        d.addCallback(lambda pod: pod.async_delete())
        return d

    @asynchronous
    def refresh(self, params):
        """Refresh a specific Pod.

        Performs pod discovery and updates all discovered information and
        discovered machines.
        """
        assert self.user.is_superuser, "Permission denied."

        @transactional
        def get_form(obj, params):
            return PodForm(instance=obj, data=params)

        @transactional
        def render_obj(obj):
            return self.full_dehydrate(obj)

        d = deferToDatabase(transactional(self.get_object), params)
        d.addCallback(partial(deferToDatabase, get_form), params)
        d.addCallback(lambda form: form.discover_and_sync_pod())
        d.addCallback(partial(deferToDatabase, render_obj))
        return d
