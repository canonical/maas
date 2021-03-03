# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Pod handler for the WebSocket connection."""


import dataclasses
from functools import partial

from django.http import HttpRequest
from twisted.internet.defer import inlineCallbacks, returnValue

from maasserver.clusterrpc.pods import (
    discover_pod_projects,
    get_best_discovered_result,
)
from maasserver.enum import NODE_TYPE
from maasserver.exceptions import PodProblem
from maasserver.forms.pods import ComposeMachineForm, PodForm
from maasserver.models.bmc import Pod
from maasserver.models.resourcepool import ResourcePool
from maasserver.models.virtualmachine import get_vm_host_resources
from maasserver.models.zone import Zone
from maasserver.permissions import PodPermission
from maasserver.rbac import rbac
from maasserver.utils.orm import reload_object, transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import (
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.drivers.pod import Capabilities
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import asynchronous

log = LegacyLogger()


class PodHandler(TimestampedModelHandler):
    class Meta:
        queryset = Pod.objects.all()
        pk = "id"
        form = PodForm
        form_requires_request = True
        allowed_methods = [
            "list",
            "get",
            "create",
            "update",
            "delete",
            "set_active",
            "refresh",
            "compose",
            "get_projects",
        ]
        exclude = [
            "bmc_type",
            "cores",
            "local_storage",
            "memory",
            "power_type",
            "power_parameters",
            "default_storage_pool",
        ]
        listen_channels = ["pod"]
        create_permission = PodPermission.create
        view_permission = PodPermission.view
        edit_permission = PodPermission.edit
        delete_permission = PodPermission.edit

    def get_queryset(self, for_list=False):
        """Return `QuerySet` for devices only viewable by `user`."""
        return Pod.objects.get_pods(
            self.user, PodPermission.view
        ).select_related("hints")

    def preprocess_form(self, action, params):
        """Process the `params` before passing the data to the form."""
        new_params = params

        if "zone" in params:
            zone = Zone.objects.get(id=params["zone"])
            new_params["zone"] = zone.name

        if "pool" in params:
            pool = ResourcePool.objects.get(id=params["pool"])
            new_params["pool"] = pool.name

        # Cleanup any fields that have a None value.
        new_params = {
            key: value
            for key, value in new_params.items()
            if value is not None
        }
        return super().preprocess_form(action, new_params)

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        if self.user.is_superuser:
            data.update(obj.power_parameters)
        data.update(
            {
                "type": obj.power_type,
                "total": self.dehydrate_total(obj),
                "used": self.dehydrate_used(obj),
                "available": self.dehydrate_available(obj),
                "composed_machines_count": obj.node_set.filter(
                    node_type=NODE_TYPE.MACHINE
                ).count(),
                "owners_count": (
                    obj.node_set.exclude(owner=None)
                    .values_list("owner")
                    .distinct()
                    .count()
                ),
                "hints": self.dehydrate_hints(obj.hints),
                "storage_pools": [
                    self.dehydrate_storage_pool(pool)
                    for pool in obj.storage_pools.all()
                ],
                "default_storage_pool": (
                    obj.default_storage_pool.pool_id
                    if obj.default_storage_pool
                    else None
                ),
                "host": obj.host.system_id if obj.host else None,
                "numa_pinning": self.dehydrate_numa_pinning(obj),
                "resources": self.dehydrate_resources(obj, for_list=for_list),
            }
        )
        if not for_list:
            if obj.host:
                data["attached_vlans"] = list(
                    obj.host.interface_set.filter(
                        vlan_id__isnull=False
                    ).values_list("vlan_id", flat=True)
                )
                boot_vlans = []
                query = obj.host.interface_set.all().prefetch_related(
                    "vlan__relay_vlan"
                )
                for interface in query:
                    if interface.has_bootable_vlan():
                        boot_vlans.append(interface.vlan_id)
                data["boot_vlans"] = boot_vlans
            else:
                data["attached_vlans"] = []
                data["boot_vlans"] = []

        if self.user.has_perm(PodPermission.compose, obj):
            data["permissions"].append("compose")

        return data

    def dehydrate_total(self, obj):
        """Dehydrate total Pod resources."""
        return {
            "cores": obj.cores,
            "memory": obj.memory,
            "memory_gb": "%.1f" % (obj.memory / 1024.0),
            "local_storage": obj.local_storage,
            "local_storage_gb": "%.1f" % (obj.local_storage / (1024 ** 3)),
        }

    def dehydrate_used(self, obj):
        """Dehydrate used Pod resources."""
        used_memory = obj.get_used_memory()
        used_local_storage = obj.get_used_local_storage()
        return {
            "cores": obj.get_used_cores(),
            "memory": used_memory,
            "memory_gb": "%.1f" % (used_memory / 1024.0),
            "local_storage": used_local_storage,
            "local_storage_gb": "%.1f" % (used_local_storage / (1024 ** 3)),
        }

    def dehydrate_available(self, obj):
        """Dehydrate available Pod resources."""
        used_memory = obj.get_used_memory()
        used_local_storage = obj.get_used_local_storage()
        return {
            "cores": obj.cores - obj.get_used_cores(),
            "memory": obj.memory - used_memory,
            "memory_gb": "%.1f" % ((obj.memory - used_memory) / 1024.0),
            "local_storage": obj.local_storage - used_local_storage,
            "local_storage_gb": "%.1f"
            % ((obj.local_storage - used_local_storage) / (1024 ** 3)),
        }

    def dehydrate_hints(self, hints):
        """Dehydrate Pod hints."""
        return {
            "cores": hints.cores,
            "cpu_speed": hints.cpu_speed,
            "memory": hints.memory,
            "memory_gb": "%.1f" % (hints.memory / 1024.0),
            "local_storage": hints.local_storage,
            "local_storage_gb": "%.1f" % (hints.local_storage / (1024 ** 3)),
        }

    def dehydrate_storage_pool(self, pool):
        """Dehydrate PodStoragePool."""
        used = pool.get_used_storage()
        return {
            "id": pool.pool_id,
            "name": pool.name,
            "type": pool.pool_type,
            "path": pool.path,
            "total": pool.storage,
            "used": used,
            "available": pool.storage - used,
        }

    def dehydrate_resources(self, obj, for_list=False):
        """Dehydrate resources info."""
        return dataclasses.asdict(
            get_vm_host_resources(obj, detailed=not for_list)
        )

    def dehydrate_numa_pinning(self, obj):
        """Dehydrate NUMA pinning info."""
        host_resources = get_vm_host_resources(obj)
        return [dataclasses.asdict(entry) for entry in host_resources.numa]

    @asynchronous
    @inlineCallbacks
    def get_projects(self, params):
        """Return projects from the specified pod."""
        pod_type = params.pop("type")
        results = yield discover_pod_projects(pod_type, params)
        projects = yield get_best_discovered_result(results)
        returnValue(projects)

    @asynchronous
    def create(self, params):
        """Create a pod."""

        @transactional
        def get_form(params):
            # Clear rbac cache before check (this is in its own thread).
            rbac.clear()

            if not self.user.has_perm(self._meta.create_permission):
                raise HandlerPermissionError()

            request = HttpRequest()
            request.user = self.user
            form = PodForm(
                data=self.preprocess_form("create", params), request=request
            )
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

        @transactional
        def get_form(params):
            # Clear rbac cache before check (this is in its own thread).
            rbac.clear()

            obj = self.get_object(params)
            if not self.user.has_perm(self._meta.edit_permission, obj):
                raise HandlerPermissionError()

            request = HttpRequest()
            request.user = self.user
            form = PodForm(
                instance=obj,
                data=self.preprocess_form("update", params),
                request=request,
            )
            if not form.is_valid():
                raise HandlerValidationError(form.errors)
            else:
                form.cleaned_data["tags"] = params["tags"]
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

        @transactional
        def get_object(params):
            # Clear rbac cache before check (this is in its own thread).
            rbac.clear()

            obj = self.get_object(params)
            if not self.user.has_perm(self._meta.delete_permission, obj):
                raise HandlerPermissionError()
            return obj

        decompose = params.get("decompose", False)
        d = deferToDatabase(get_object, params)
        d.addCallback(lambda pod: pod.async_delete(decompose=decompose))
        return d

    @asynchronous
    def refresh(self, params):
        """Refresh a specific Pod.

        Performs pod discovery and updates all discovered information and
        discovered machines.
        """

        @transactional
        def get_form(obj, params):
            # Clear rbac cache before check (this is in its own thread).
            rbac.clear()

            obj = self.get_object(params)
            if not self.user.has_perm(self._meta.edit_permission, obj):
                raise HandlerPermissionError()

            request = HttpRequest()
            request.user = self.user
            return PodForm(
                instance=obj,
                data=self.preprocess_form("refresh", params),
                request=request,
            )

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

        @transactional
        def get_object(params):
            # Running inside new database thread, be sure the rbac cache is
            # cleared so accessing information will not be already cached.
            rbac.clear()
            obj = self.get_object(params)
            if not self.user.has_perm(PodPermission.compose, obj):
                raise HandlerPermissionError()
            return obj

        def composable(obj):
            if Capabilities.COMPOSABLE not in obj.capabilities:
                raise HandlerValidationError(
                    "Pod does not support composability."
                )
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
                "Pod unable to compose machine: %s" % str(failure.value)
            )

        def compose(result, params):
            form, obj = result
            d = form.compose(
                skip_commissioning=params.get("skip_commissioning", False)
            )
            d.addCallback(lambda machine: (machine, obj))
            d.addErrback(wrap_errors)
            return d

        @transactional
        def render_obj(result):
            _, obj = result
            return self.full_dehydrate(reload_object(obj))

        d = deferToDatabase(get_object, params)
        d.addCallback(composable)
        d.addCallback(partial(deferToDatabase, get_form), params)
        d.addCallback(compose, params)
        d.addCallback(partial(deferToDatabase, render_obj))
        return d
