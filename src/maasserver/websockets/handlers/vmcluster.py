# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.models import VMCluster
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import dehydrate_datetime
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
        ]

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
                "free": resources.cores.free,
            },
            "memory": {
                "hugepages": {
                    "total": resources.memory.hugepages.total,
                    "free": resources.memory.hugepages.free,
                },
                "general": {
                    "total": resources.memory.general.total,
                    "free": resources.memory.general.free,
                },
            },
            "storage": {
                "total": resources.storage.total,
                "free": resources.storage.free,
            },
            "vm_count": resources.vm_count.tracked,
            "storage_pools": {
                n: {"free": p.free, "total": p.total}
                for n, p in resources.storage_pools.items()
            },
        }

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
            "created_at": dehydrate_datetime(cluster.created),
        }

    async def list(self, params):
        @transactional
        def get_objects(params):
            return VMCluster.objects.all()

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
            return VMCluster.objects.group_by_physical_cluster(self.user)

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
            return VMCluster.objects.get(id=id)

        @transactional
        def render_object(obj):
            return self.dehydrate(
                obj, obj.hosts(), obj.total_resources(), obj.virtual_machines()
            )

        cluster = await deferToDatabase(get_object, params["id"])
        return await deferToDatabase(render_object, cluster)
