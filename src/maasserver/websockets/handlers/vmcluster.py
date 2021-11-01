# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.models import VMCluster
from maasserver.permissions import VMClusterPermission
from maasserver.rbac import rbac
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import HandlerPermissionError
from maasserver.websockets.handlers.timestampedmodel import (
    TimestampedModelHandler,
)


class VMClusterHandler(TimestampedModelHandler):
    class Meta:
        queryset = VMCluster.objects.all()
        pk = "id"
        allowed_methods = [
            "list",
            "list_by_physical_cluster",
            "get",
            "delete",
        ]
        listen_channels = ["vmcluster"]
        view_permission = VMClusterPermission.view
        delete_permission = VMClusterPermission.delete

    def _dehydrate_vmhost(self, vmhost):
        return {
            "id": vmhost.id,
            "name": vmhost.name,
            "project": vmhost.tracked_project,
            "tags": vmhost.tags,
            "resource_pool": vmhost.pool.name,
            "availability_zone": vmhost.zone.name,
        }

    def _dehydrate_virtual_machine(self, vm):
        return {
            "system_id": vm.machine.system_id,
            "name": vm.machine.hostname,
            "project": vm.project,
            "hugepages_enabled": vm.hugepages_backed,
            "pinned_cores": vm.pinned_cores,
            "unpinned_cores": vm.unpinned_cores,
        }

    def _dehydrate_resources(self, resources):
        return {
            "cpu": {
                "total": resources.cores.total,
                "allocated_tracked": resources.cores.allocated_tracked,
                "allocated_other": resources.cores.allocated_other,
                "free": resources.cores.free,
            },
            "memory": {
                "hugepages": {
                    "total": resources.memory.hugepages.total,
                    "allocated_tracked": resources.memory.hugepages.allocated_tracked,
                    "allocated_other": resources.memory.hugepages.allocated_other,
                    "free": resources.memory.hugepages.free,
                },
                "general": {
                    "total": resources.memory.general.total,
                    "allocated_tracked": resources.memory.general.allocated_tracked,
                    "allocated_other": resources.memory.general.allocated_other,
                    "free": resources.memory.general.free,
                },
            },
            "storage": {
                "total": resources.storage.total,
                "allocated_tracked": resources.storage.allocated_tracked,
                "allocated_other": resources.storage.allocated_other,
                "free": resources.storage.free,
            },
            "vm_count": resources.vm_count.tracked,
            "storage_pools": {
                n: {"free": p.free, "total": p.total}
                for n, p in resources.storage_pools.items()
            },
        }

    def full_dehydrate(self, obj, for_list=False):
        return self.dehydrate(
            obj, obj.hosts(), obj.total_resources(), obj.virtual_machines()
        )

    def dehydrate(self, cluster, vmhosts, resources, vms):
        return {
            "id": cluster.id,
            "name": cluster.name,
            "project": cluster.project,
            "hosts": [self._dehydrate_vmhost(vmhost) for vmhost in vmhosts],
            "total_resources": self._dehydrate_resources(resources),
            "virtual_machines": [
                self._dehydrate_virtual_machine(vm) for vm in vms
            ],
            "resource_pool": (
                cluster.pool.id if cluster.pool is not None else ""
            ),
            "availability_zone": cluster.zone.id,
            "version": (vmhosts[0].version if len(vmhosts) > 0 else ""),
            "created_at": self.dehydrate_created(cluster.created),
            "updated_at": self.dehydrate_updated(cluster.updated),
        }

    async def list(self, params):
        @transactional
        def get_objects(params):
            # Clear rbac cache before check (this is in its own thread).
            rbac.clear()
            return VMCluster.objects.get_clusters(
                self.user, self._meta.view_permission
            )

        @transactional
        def render_objects(objs):
            return {
                cluster.name: self.dehydrate(
                    cluster,
                    cluster.hosts(),
                    cluster.total_resources(),
                    cluster.virtual_machines(),
                )
                for cluster in objs
            }

        clusters = await deferToDatabase(get_objects, params)

        return await deferToDatabase(render_objects, clusters)

    async def list_by_physical_cluster(self, params):
        @transactional
        def get_objects(params):
            return VMCluster.objects.group_by_physical_cluster(
                self.user, self._meta.view_permission
            )

        @transactional
        def render_objects(objs):
            return [
                [
                    self.dehydrate(
                        cluster,
                        cluster.hosts(),
                        cluster.total_resources(),
                        cluster.virtual_machines(),
                    )
                    for cluster in phys_cluster
                ]
                for phys_cluster in objs
            ]

        clusters = await deferToDatabase(get_objects, params)

        return await deferToDatabase(render_objects, clusters)

    async def get(self, params):
        @transactional
        def get_object(id):
            return VMCluster.objects.get_cluster_or_404(
                id=id, user=self.user, perm=self._meta.view_permission
            )

        @transactional
        def render_object(obj):
            return self.dehydrate(
                obj, obj.hosts(), obj.total_resources(), obj.virtual_machines()
            )

        cluster = await deferToDatabase(get_object, params["id"])
        return await deferToDatabase(render_object, cluster)

    async def delete(self, params):
        """Delete the object."""

        @transactional
        def get_one_vmhost(params):
            # Clear rbac cache before check (this is in its own thread).
            rbac.clear()

            obj = self.get_object(params)
            if not self.user.has_perm(self._meta.delete_permission, obj):
                raise HandlerPermissionError()
            return obj.hosts()[0]

        decompose = params.get("decompose", False)
        vmhost = await deferToDatabase(get_one_vmhost, params)
        # delete the 1st VMHost, the others and the cluster itself will follow
        return await vmhost.async_delete(
            decompose=decompose, delete_peers=True
        )
