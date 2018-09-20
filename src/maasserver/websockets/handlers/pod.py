# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Pod handler for the WebSocket connection."""

__all__ = [
    "PodHandler",
]

from functools import partial

from django.http import HttpRequest
from maasserver.enum import NODE_TYPE
from maasserver.exceptions import PodProblem
from maasserver.forms.pods import (
    ComposeMachineForm,
    PodForm,
)
from maasserver.models.bmc import Pod
from maasserver.models.resourcepool import ResourcePool
from maasserver.models.zone import Zone
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
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import asynchronous


log = LegacyLogger()


class PodHandler(TimestampedModelHandler):

    class Meta:
        queryset = Pod.objects.all().select_related('hints')
        pk = 'id'
        form = PodForm
        form_requires_request = True
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'delete',
            'set_active',
            'refresh',
            'compose',
        ]
        exclude = [
            'bmc_type',
            'cores',
            'local_disks',
            'local_storage',
            'iscsi_storage',
            'memory',
            'power_type',
            'power_parameters',
            'default_storage_pool',
        ]
        listen_channels = [
            "pod",
        ]

    def preprocess_form(self, action, params):
        """Process the `params` before passing the data to the form."""
        new_params = params

        if "zone" in params:
            zone = Zone.objects.get(id=params['zone'])
            new_params["zone"] = zone.name

        if "pool" in params:
            pool = ResourcePool.objects.get(id=params['pool'])
            new_params["pool"] = pool.name

        # Cleanup any fields that have a None value.
        new_params = {
            key: value
            for key, value in new_params.items()
            if value is not None
        }
        return super(PodHandler, self).preprocess_form(action, new_params)

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        if reload_object(self.user).is_superuser:
            data.update(obj.power_parameters)
        data["type"] = obj.power_type
        data["total"] = self.dehydrate_total(obj)
        data["used"] = self.dehydrate_used(obj)
        data["available"] = self.dehydrate_available(obj)
        data["composed_machines_count"] = obj.node_set.filter(
            node_type=NODE_TYPE.MACHINE).count()
        data["hints"] = self.dehydrate_hints(obj.hints)
        if not for_list:
            storage_pools = obj.storage_pools.all()
            if len(storage_pools) > 0:
                pools_data = []
                for pool in storage_pools:
                    pools_data.append(self.dehydrate_storage_pool(pool))
                data["storage_pools"] = pools_data
                data["default_storage_pool"] = obj.default_storage_pool.pool_id
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
        if Capabilities.ISCSI_STORAGE in obj.capabilities:
            result['iscsi_storage'] = obj.iscsi_storage
            result['iscsi_storage_gb'] = '%.1f' % (
                obj.iscsi_storage / (1024 ** 3))
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
        if Capabilities.ISCSI_STORAGE in obj.capabilities:
            used_iscsi_storage = obj.get_used_iscsi_storage()
            result['iscsi_storage'] = used_iscsi_storage
            result['iscsi_storage_gb'] = '%.1f' % (
                used_iscsi_storage / (1024 ** 3))
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
        if Capabilities.ISCSI_STORAGE in obj.capabilities:
            used_iscsi_storage = obj.get_used_iscsi_storage()
            result['iscsi_storage'] = obj.iscsi_storage - used_iscsi_storage
            result['iscsi_storage_gb'] = '%.1f' % (
                (obj.iscsi_storage - used_iscsi_storage) / (1024 ** 3))
        return result

    def dehydrate_hints(self, hints):
        """Dehydrate Pod hints."""
        return {
            'cores': hints.cores,
            'cpu_speed': hints.cpu_speed,
            'memory': hints.memory,
            'memory_gb': '%.1f' % (hints.memory / 1024.0),
            'local_storage': hints.local_storage,
            'local_storage_gb': '%.1f' % (
                hints.local_storage / (1024 ** 3)),
            'local_disks': hints.local_disks,
            'iscsi_storage': hints.iscsi_storage,
            'iscsi_storage_gb': '%.1f' % (
                hints.iscsi_storage / (1024 ** 3)),
        }

    def dehydrate_storage_pool(self, pool):
        """Dehydrate PodStoragePool."""
        used = pool.get_used_storage()
        return {
            'id': pool.pool_id,
            'name': pool.name,
            'type': pool.pool_type,
            'path': pool.path,
            'total': pool.storage,
            'used': used,
            'available': pool.storage - used,
        }

    @asynchronous
    def create(self, params):
        """Create a pod."""
        assert self.user.is_superuser, "Permission denied."

        @transactional
        def get_form(params):
            request = HttpRequest()
            request.user = self.user
            form = PodForm(
                data=self.preprocess_form("create", params), request=request)
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
    def update(self, params):
        """Update a pod."""
        assert self.user.is_superuser, "Permission denied."

        @transactional
        def get_form(params):
            obj = self.get_object(params)
            request = HttpRequest()
            request.user = self.user
            form = PodForm(
                instance=obj, data=self.preprocess_form("update", params),
                request=request)
            if not form.is_valid():
                raise HandlerValidationError(form.errors)
            else:
                form.cleaned_data['tags'] = params['tags']
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
            request = HttpRequest()
            request.user = self.user
            return PodForm(
                instance=obj, data=self.preprocess_form("refresh", params),
                request=request)

        @transactional
        def render_obj(obj):
            return self.full_dehydrate(obj)

        d = deferToDatabase(transactional(self.get_object), params)
        d.addCallback(partial(deferToDatabase, get_form), params)
        d.addCallback(lambda form: form.discover_and_sync_pod())
        d.addCallback(partial(deferToDatabase, render_obj))
        return d

    @asynchronous
    def compose(self, params):
        """Compose a machine in a Pod."""
        assert self.user.is_superuser, "Permission denied."

        def composable(obj):
            if Capabilities.COMPOSABLE not in obj.capabilities:
                raise HandlerValidationError(
                    "Pod does not support composability.")
            return obj

        @transactional
        def get_form(obj, params):
            request = HttpRequest()
            request.user = self.user
            form = ComposeMachineForm(pod=obj, data=params, request=request)
            if not form.is_valid():
                raise HandlerValidationError(form.errors)
            return form, obj

        def wrap_errors(failure):
            log.err(failure, "Failed to compose machine.")
            raise PodProblem(
                "Pod unable to compose machine: %s" % str(failure.value))

        def compose(result, params):
            form, obj = result
            d = form.compose(
                skip_commissioning=params.get('skip_commissioning', False))
            d.addCallback(lambda machine: (machine, obj))
            d.addErrback(wrap_errors)
            return d

        @transactional
        def render_obj(result):
            _, obj = result
            return self.full_dehydrate(reload_object(obj))

        d = deferToDatabase(transactional(self.get_object), params)
        d.addCallback(composable)
        d.addCallback(partial(deferToDatabase, get_form), params)
        d.addCallback(compose, params)
        d.addCallback(partial(deferToDatabase, render_obj))
        return d
