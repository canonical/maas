# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.handlers import VMClusterHandler
from maastesting.crochet import wait_for

wait_for_reactor = wait_for(30)  # 30 seconds.


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
                    bmc=vmhost.as_bmc(), machine=factory.make_Machine()
                )
                for vmhost in vmhosts
            ]
            cluster_group.append((cluster, vmhosts, vms))

        return cluster_group

    def make_physical_cluster_group(self):
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
                vms = [
                    factory.make_VirtualMachine(
                        bmc=vmhost.as_bmc(), machine=factory.make_Machine()
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
            self.assertEqual(
                pool.free,
                result["total_resources"]["storage_pools"][name]["free"],
            )

    def test_dehydrate(self):
        cluster = factory.make_VMCluster(pods=0)
        vmhosts = [factory.make_Pod(cluster=cluster) for _ in range(3)]
        _ = [factory.make_PodStoragePool(pod=pod) for pod in vmhosts]

        vms = [
            factory.make_VirtualMachine(
                bmc=vmhost.as_bmc(), machine=factory.make_Machine()
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
    async def test_get(self):
        cluster = await deferToDatabase(factory.make_VMCluster)
        admin = await deferToDatabase(factory.make_admin)

        handler = VMClusterHandler(admin, {}, None)

        result = await handler.get({"id": cluster.id})

        self.assertEqual(cluster.name, result["name"])
        self.assertEqual(cluster.project, result["project"])
        self.assertEqual(1, len(result["hosts"]))
        self.assertEqual([], result["virtual_machines"])
