# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The Pod handler for the WebSocket connection."""

import dataclasses

import attr
from django.http import HttpRequest

from maasserver.clusterrpc.pods import (
    discover_pod_projects,
    get_best_discovered_result,
)
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
from maasserver.vmhost import (
    discover_and_sync_vmhost,
    discover_and_sync_vmhost_async,
)
from maasserver.websockets.base import (
    dehydrate_certificate,
    HandlerPermissionError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)
from provisioningserver.certificates import Certificate
from provisioningserver.drivers.pod import Capabilities
from provisioningserver.logger import LegacyLogger

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
        data.update(
            {
                "type": obj.power_type,
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
                "resources": self.dehydrate_resources(obj, for_list=for_list),
            }
        )
        if self.user.is_superuser:
            data["power_parameters"] = obj.get_power_parameters()
        if not for_list:
            if obj.host:
                data["attached_vlans"] = list(
                    obj.host.current_config.interface_set.filter(
                        vlan_id__isnull=False
                    ).values_list("vlan_id", flat=True)
                )
                boot_vlans = []
                query = obj.host.current_config.interface_set.all().prefetch_related(
                    "vlan__relay_vlan"
                )
                for interface in query:
                    if interface.has_bootable_vlan():
                        boot_vlans.append(interface.vlan_id)
                data["boot_vlans"] = boot_vlans
            else:
                data["attached_vlans"] = []
                data["boot_vlans"] = []

            # include certificate info if present
            certificate = obj.get_power_parameters().get("certificate")
            key = obj.get_power_parameters().get("key")
            if certificate and key:
                cert = Certificate.from_pem(certificate, key)
                data["certificate"] = dehydrate_certificate(cert)

        if self.user.has_perm(PodPermission.compose, obj):
            data["permissions"].append("compose")

        if obj.hints.cluster:
            data["cluster"] = obj.hints.cluster_id

        return data

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

    async def get_projects(self, params):
        """Return projects from the specified pod."""
        pod_type = params.pop("type")
        results = await discover_pod_projects(pod_type, params)
        projects = get_best_discovered_result(results)
        return [attr.asdict(project) for project in projects]

    async def create(self, params):
        """Create a pod."""

        @transactional
        def create_obj(params):
            # Clear rbac cache before check (this is in its own thread).
            rbac.clear()

            if not self.user.has_perm(self._meta.create_permission):
                raise HandlerPermissionError()

            request = HttpRequest()
            request.user = self.user
            form = PodForm(
                data=self.preprocess_form("create", params), request=request
            )
            if form.is_valid():
                return form.save()
            else:
                raise HandlerValidationError(form.errors)

        @transactional
        def render_obj(obj):
            return self.full_dehydrate(obj)

        pod = await deferToDatabase(create_obj, params)
        pod = await deferToDatabase(self._try_sync_and_save, pod)
        return await deferToDatabase(render_obj, pod)

    async def update(self, params):
        """Update a pod."""

        @transactional
        def update_obj(params):
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
            if form.is_valid():
                form.cleaned_data["tags"] = params["tags"]
                return form.save()
            else:
                raise HandlerValidationError(form.errors)

        @transactional
        def render_obj(obj):
            return self.full_dehydrate(obj)

        pod = await deferToDatabase(update_obj, params)
        pod = await deferToDatabase(self._try_sync_and_save, pod)
        return await deferToDatabase(render_obj, pod)

    async def delete(self, params):
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
        pod = await deferToDatabase(get_object, params)
        return await pod.async_delete(decompose=decompose)

    async def refresh(self, params):
        """Refresh a specific Pod.

        Performs pod discovery and updates all discovered information and
        discovered machines.
        """

        @transactional
        def get_object(params):
            # Clear rbac cache before check (this is in its own thread).
            rbac.clear()

            obj = self.get_object(params)
            if not self.user.has_perm(self._meta.edit_permission, obj):
                raise HandlerPermissionError()

            return obj

        @transactional
        def render_obj(obj):
            return self.full_dehydrate(obj)

        pod = await deferToDatabase(transactional(self.get_object), params)
        await discover_and_sync_vmhost_async(pod, self.user)
        return await deferToDatabase(render_obj, pod)

    async def compose(self, params):
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

        @transactional
        def get_form(obj, params):
            request = HttpRequest()
            request.user = self.user
            form = ComposeMachineForm(pod=obj, data=params, request=request)
            if not form.is_valid():
                raise HandlerValidationError(form.errors)
            return form

        @transactional
        def render_obj(obj):
            return self.full_dehydrate(reload_object(obj))

        pod = await deferToDatabase(get_object, params)
        if Capabilities.COMPOSABLE not in pod.capabilities:
            raise HandlerValidationError("Pod does not support composability.")
        form = await deferToDatabase(get_form, pod, params)
        try:
            await form.compose(
                skip_commissioning=params.get("skip_commissioning", False)
            )
        except Exception as error:
            log.err(error, "Failed to compose machine.")
            raise PodProblem("Pod unable to compose machine: %s" % str(error))  # noqa: B904
        return await deferToDatabase(render_obj, pod)

    @transactional
    def _try_sync_and_save(self, pod):
        try:
            discover_and_sync_vmhost(pod, self.user)
        except PodProblem:
            # if discovery fails, still save the object as is, to allow config
            # changes
            pod.save()
        return pod
