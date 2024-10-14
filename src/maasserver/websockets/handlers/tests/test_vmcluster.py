# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from django.http import Http404
from twisted.internet.defer import succeed

from maasserver.models import Pod
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import DATETIME_FORMAT
from maasserver.websockets.handlers import VMClusterHandler
from maastesting.crochet import wait_for

wait_for_reactor = wait_for()


class TestVMClusterHandler(MAASTransactionServerTestCase):
    def make_cluster_group(self):
        cluster_group = []
        pool = factory.make_ResourcePool()

        for _ in range(3):
            cluster = factory.make_VMCluster(pool=pool, pods=0)
            vmhosts = [
                factory.make_Pod(cluster=cluster, pod_type="lxd")
                for _ in range(3)
            ]
            vms = [
                factory.make_VirtualMachine(
                    bmc=vmhost.as_bmc(),
                    machine=factory.make_Machine(),
                    project=cluster.project,
                )
                for vmhost in vmhosts
            ]
            cluster_group.append((cluster, vmhosts, vms))

        return cluster_group

    def make_physical_cluster_group(self, with_vms=True):
        cluster_groups = []

        for _ in range(2):
            address_group = [factory.make_ip_address() for _ in range(3)]
            cluster_group = []
            for _ in range(3):
                cluster = factory.make_VMCluster(pods=0)
                vmhosts = [
                    factory.make_Pod(
                        parameters={
                            "power_address": address,
                            "project": cluster.project,
                        },
                        cluster=cluster,
                        pod_type="lxd",
                    )
                    for address in address_group
                ]
                vms = []
                if with_vms:
                    vms = [
                        factory.make_VirtualMachine(
                            bmc=vmhost.as_bmc(),
                            machine=factory.make_Machine(),
                            project=cluster.project,
                        )
                        for vmhost in vmhosts
                    ]
                cluster_group.append((cluster, vmhosts, vms))
            cluster_groups.append(cluster_group)

        return cluster_groups

    def _assert_dehydrated_cluster_equal(self, result, cluster, vmhosts, vms):
        self.assertEqual(result["id"], cluster.id)
        self.assertEqual(result["name"], cluster.name)
        self.assertEqual(result["project"], cluster.project)
        self.assertEqual(result["availability_zone"], cluster.zone.id)
        self.assertEqual(
            result["version"], vmhosts[0].version if len(vmhosts) > 0 else ""
        )
        self.assertEqual(
            result["resource_pool"],
            cluster.pool.id if cluster.pool is not None else "",
        )
        self.assertEqual(
            datetime.strptime(
                result["created_at"], DATETIME_FORMAT
            ).astimezone(),
            cluster.created.replace(microsecond=0),
        )

        expected_vmhosts = [
            {
                "id": vmhost.id,
                "name": vmhost.name,
                "project": vmhost.tracked_project,
                "tags": vmhost.tags,
                "resource_pool": vmhost.pool.name,
                "availability_zone": vmhost.zone.name,
            }
            for vmhost in vmhosts
        ]
        self.assertCountEqual(result["hosts"], expected_vmhosts)

        expected_vms = [
            {
                "system_id": vm.machine.system_id,
                "name": vm.machine.hostname,
                "project": vm.project,
                "hugepages_enabled": vm.hugepages_backed,
                "pinned_cores": vm.pinned_cores,
                "unpinned_cores": vm.unpinned_cores,
            }
            for vm in vms
        ]
        self.assertCountEqual(result["virtual_machines"], expected_vms)

        resources = cluster.total_resources()
        self.assertEqual(
            resources.cores.total, result["total_resources"]["cpu"]["total"]
        )
        self.assertEqual(
            resources.memory.general.total,
            result["total_resources"]["memory"]["general"]["total"],
        )
        self.assertEqual(
            resources.memory.hugepages.total,
            result["total_resources"]["memory"]["hugepages"]["total"],
        )
        self.assertEqual(
            resources.storage.total,
            result["total_resources"]["storage"]["total"],
        )
        self.assertEqual(
            resources.cores.allocated_tracked,
            result["total_resources"]["cpu"]["allocated_tracked"],
        )
        self.assertEqual(
            resources.memory.general.allocated_tracked,
            result["total_resources"]["memory"]["general"][
                "allocated_tracked"
            ],
        )
        self.assertEqual(
            resources.memory.hugepages.allocated_tracked,
            result["total_resources"]["memory"]["hugepages"][
                "allocated_tracked"
            ],
        )
        self.assertEqual(
            resources.storage.allocated_tracked,
            result["total_resources"]["storage"]["allocated_tracked"],
        )
        self.assertEqual(
            resources.cores.allocated_tracked,
            result["total_resources"]["cpu"]["allocated_other"],
        )
        self.assertEqual(
            resources.memory.general.allocated_tracked,
            result["total_resources"]["memory"]["general"]["allocated_other"],
        )
        self.assertEqual(
            resources.memory.hugepages.allocated_tracked,
            result["total_resources"]["memory"]["hugepages"][
                "allocated_other"
            ],
        )
        self.assertEqual(
            resources.storage.allocated_tracked,
            result["total_resources"]["storage"]["allocated_other"],
        )
        self.assertEqual(
            resources.cores.free, result["total_resources"]["cpu"]["free"]
        )
        self.assertEqual(
            resources.memory.general.free,
            result["total_resources"]["memory"]["general"]["free"],
        )
        self.assertEqual(
            resources.memory.hugepages.free,
            result["total_resources"]["memory"]["hugepages"]["free"],
        )
        self.assertEqual(
            resources.storage.free,
            result["total_resources"]["storage"]["free"],
        )
        self.assertEqual(
            resources.vm_count.tracked, result["total_resources"]["vm_count"]
        )
        for name, pool in resources.storage_pools.items():
            self.assertIn(name, result["total_resources"]["storage_pools"])
            ret_pool = result["total_resources"]["storage_pools"][name]
            self.assertEqual(pool.backend, ret_pool["backend"])
            self.assertEqual(pool.path, ret_pool["path"])
            self.assertEqual(pool.free, ret_pool["free"])
            self.assertEqual(pool.total, ret_pool["total"])
            self.assertEqual(
                pool.allocated_tracked, ret_pool["allocated_tracked"]
            )
            self.assertEqual(pool.allocated_other, ret_pool["allocated_other"])

    def test_full_dehydrate(self):
        cluster = factory.make_VMCluster(pods=3)
        vmhosts = cluster.hosts()
        [factory.make_PodStoragePool(pod=vmhost) for vmhost in vmhosts]

        vms = [
            factory.make_VirtualMachine(
                bmc=vmhost.as_bmc(),
                machine=factory.make_Machine(),
                project=cluster.project,
            )
            for vmhost in vmhosts
        ]

        handler = VMClusterHandler(factory.make_admin(), {}, None)

        result = handler.full_dehydrate(cluster)

        self._assert_dehydrated_cluster_equal(result, cluster, vmhosts, vms)

    def test_full_dehydrate_with_untracked_vms(self):
        cluster = factory.make_VMCluster()
        vmhost = cluster.hosts().get()
        factory.make_PodStoragePool(pod=vmhost)

        tracked_vm = factory.make_VirtualMachine(
            bmc=vmhost.as_bmc(),
            machine=factory.make_Machine(),
            project=cluster.project,
        )
        # Untracked VM in a separate project
        factory.make_VirtualMachine(
            bmc=vmhost.as_bmc(),
            machine=None,
            project=factory.make_name("project"),
        )

        handler = VMClusterHandler(factory.make_admin(), {}, None)

        result = handler.full_dehydrate(cluster)

        self._assert_dehydrated_cluster_equal(
            result, cluster, [vmhost], [tracked_vm]
        )

    def test_dehydrate(self):
        cluster = factory.make_VMCluster(pods=0)
        vmhosts = [factory.make_Pod(cluster=cluster) for _ in range(3)]
        _ = [factory.make_PodStoragePool(pod=pod) for pod in vmhosts]

        vms = [
            factory.make_VirtualMachine(
                bmc=vmhost.as_bmc(),
                machine=factory.make_Machine(),
                project=cluster.project,
            )
            for vmhost in vmhosts
        ]

        handler = VMClusterHandler(factory.make_admin(), {}, None)

        result = handler.dehydrate(
            cluster, vmhosts, cluster.total_resources(), vms
        )
        self._assert_dehydrated_cluster_equal(result, cluster, vmhosts, vms)

    @wait_for_reactor
    async def test_list(self):
        cluster_group = await deferToDatabase(self.make_cluster_group)
        admin = await deferToDatabase(factory.make_admin)

        handler = VMClusterHandler(admin, {}, None)

        result = await handler.list(None)

        for cluster in cluster_group:
            await deferToDatabase(
                self._assert_dehydrated_cluster_equal,
                result[cluster[0].name],
                cluster[0],
                cluster[1],
                cluster[2],
            )

    @wait_for_reactor
    async def test_list_by_physical_cluster(self):
        cluster_groups = await deferToDatabase(
            self.make_physical_cluster_group
        )
        admin = await deferToDatabase(factory.make_admin)

        handler = VMClusterHandler(admin, {}, None)

        result = await handler.list_by_physical_cluster(None)

        expected_ids = [
            [cluster[0].id for cluster in cluster_group]
            for cluster_group in cluster_groups
        ]
        result_ids = [
            [cluster["id"] for cluster in cluster_group]
            for cluster_group in result
        ]

        self.assertCountEqual(result_ids, expected_ids)

    @wait_for_reactor
    async def test_list_by_physical_cluster_no_vms(self):
        await deferToDatabase(
            self.make_physical_cluster_group,
            with_vms=False,
        )
        admin = await deferToDatabase(factory.make_admin)

        handler = VMClusterHandler(admin, {}, None)

        result = await handler.list_by_physical_cluster(None)
        for group in result:
            for cluster in group:
                self.assertCountEqual([], cluster["virtual_machines"])

    @wait_for_reactor
    async def test_get(self):
        cluster = await deferToDatabase(factory.make_VMCluster)
        admin = await deferToDatabase(factory.make_admin)

        handler = VMClusterHandler(admin, {}, None)

        result = await handler.get({"id": cluster.id})

        self.assertEqual(cluster.name, result["name"])
        self.assertEqual(cluster.project, result["project"])
        self.assertEqual(1, len(result["hosts"]))
        self.assertEqual([], result["virtual_machines"])

    @wait_for_reactor
    async def test_delete(self):
        cluster = await deferToDatabase(factory.make_VMCluster)
        admin = await deferToDatabase(factory.make_admin)

        handler = VMClusterHandler(admin, {}, None)

        await handler.delete({"id": cluster.id})
        expected_vmcluster = await deferToDatabase(reload_object, cluster)
        self.assertIsNone(expected_vmcluster)

    @wait_for_reactor
    async def test_delete_returns_404_on_invalid_id(self):
        cluster = await deferToDatabase(factory.make_VMCluster)
        admin = await deferToDatabase(factory.make_admin)

        handler = VMClusterHandler(admin, {}, None)

        try:
            await handler.delete({"id": -1 * cluster.id})
        except Exception as e:
            self.assertIsInstance(e, Http404)
        else:
            self.fail("did not raise expected 'Http404' exception")

    @wait_for_reactor
    async def test_delete_decompose(self):
        cluster = await deferToDatabase(factory.make_VMCluster, pods=2)
        admin = await deferToDatabase(factory.make_admin)

        mock_async_delete = self.patch(Pod, "async_delete")
        mock_async_delete.return_value = succeed(None)

        handler = VMClusterHandler(admin, {}, None)

        await handler.delete({"id": cluster.id, "decompose": True})
        expected_vmcluster = await deferToDatabase(reload_object, cluster)

        self.assertIsNone(expected_vmcluster)
        self.assertEqual(2, mock_async_delete.call_count)
        mock_async_delete.assert_called_with(
            decompose=True, delete_peers=False
        )

    @wait_for_reactor
    async def test_update(self):
        cluster = await deferToDatabase(factory.make_VMCluster)
        admin = await deferToDatabase(factory.make_admin)

        zone = await deferToDatabase(factory.make_Zone)
        cluster_info = {}
        cluster_info["id"] = cluster.id
        cluster_info["zone"] = zone.name
        cluster_info["name"] = factory.make_name("cluster")

        handler = VMClusterHandler(admin, {}, None)
        updated_pod = await handler.update(cluster_info)

        self.assertEqual(cluster_info["name"], updated_pod["name"])
