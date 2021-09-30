from maasserver.models.virtualmachine import MB
from maasserver.models.vmcluster import VMCluster
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestVMClusterManager(MAASServerTestCase):
    def test_group_by_physical_cluster(self):
        cluster_groups = [
            [factory.make_VMCluster() for _ in range(3)] for _ in range(3)
        ]

        for i, cluster_group in enumerate(cluster_groups):
            address_group = [factory.make_StaticIPAddress() for _ in range(3)]
            for cluster in cluster_group:
                for address in address_group:
                    factory.make_Pod(
                        cluster=cluster,
                        parameters={
                            "project": cluster.project,
                            "power_address": "%s:8443" % address,
                        },
                        pod_type="lxd",
                    )

        results = VMCluster.objects.group_by_physical_cluster()
        self.assertCountEqual(results, cluster_groups)


class TestVMCluster(MAASServerTestCase):
    def test_hosts(self):
        cluster_name = factory.make_name("name")
        project = factory.make_name("project")
        cluster = VMCluster(name=cluster_name, project=project)
        pods = []
        for _ in range(0, 3):
            pods.append(
                factory.make_Pod(
                    pod_type="lxd", host=factory.make_Node(), cluster=cluster
                )
            )

        hosts = list(cluster.hosts())

        for pod in pods:
            self.assertIn(pod, hosts)

    def test_hosts_with_no_registered_hosts(self):
        cluster_name = factory.make_name("name")
        project = factory.make_name("project")
        cluster = VMCluster(name=cluster_name, project=project)
        self.assertEqual(list(cluster.hosts()), [])

    def test_allocated_total_resources(self):
        cluster_name = factory.make_name("name")
        project = factory.make_name("project")
        cluster = VMCluster(name=cluster_name, project=project)
        for _ in range(0, 3):
            pod = factory.make_Pod(
                pod_type="lxd",
                host=None,
                cores=8,
                memory=4096,
                cluster=cluster,
            )
            node = factory.make_Node(bmc=pod)
            factory.make_VirtualMachine(
                machine=node,
                memory=1024,
                pinned_cores=[0, 2],
                hugepages_backed=False,
                bmc=pod,
            )

        resources = cluster.total_resources()
        self.assertEqual(resources.cores.allocated, 6)
        self.assertEqual(resources.cores.free, 18)
        self.assertEqual(resources.memory.general.free, 9216 * MB)
        self.assertEqual(resources.memory.general.allocated, 3072 * MB)
        self.assertEqual(resources.memory.hugepages.free, 0)
        self.assertEqual(resources.memory.hugepages.allocated, 0)
        self.assertEqual(resources.storage.allocated, 0)
        self.assertEqual(resources.storage.free, 0)

    def test_no_allocated_total_resources(self):
        cluster_name = factory.make_name("name")
        project = factory.make_name("project")
        cluster = VMCluster(name=cluster_name, project=project)
        for _ in range(0, 3):
            pod = factory.make_Pod(
                pod_type="lxd",
                host=None,
                cores=8,
                memory=4096,
                cluster=cluster,
            )
            factory.make_Node(bmc=pod)

        resources = cluster.total_resources()
        self.assertEqual(resources.cores.allocated, 0)
        self.assertEqual(resources.cores.free, 24)
        self.assertEqual(resources.memory.general.free, 3 * 4096 * MB)
        self.assertEqual(resources.memory.general.allocated, 0)
        self.assertEqual(resources.memory.hugepages.free, 0)
        self.assertEqual(resources.memory.hugepages.allocated, 0)
        self.assertEqual(resources.storage.allocated, 0)
        self.assertEqual(resources.storage.free, 0)

    def test_no_hosts_total_resources(self):
        cluster_name = factory.make_name("name")
        project = factory.make_name("project")
        cluster = VMCluster(name=cluster_name, project=project)
        resources = cluster.total_resources()
        self.assertEqual(resources.cores.allocated, 0)
        self.assertEqual(resources.cores.free, 0)
        self.assertEqual(resources.memory.general.free, 0)
        self.assertEqual(resources.memory.general.allocated, 0)
        self.assertEqual(resources.memory.hugepages.free, 0)
        self.assertEqual(resources.memory.hugepages.allocated, 0)
        self.assertEqual(resources.storage.allocated, 0)
        self.assertEqual(resources.storage.free, 0)

    def test_virtual_machines(self):
        cluster_name = factory.make_name("name")
        project = factory.make_name("project")
        cluster = VMCluster(name=cluster_name, project=project)
        expected_vms = []
        for _ in range(0, 3):
            pod = factory.make_Pod(
                pod_type="lxd",
                host=None,
                cores=8,
                memory=4096,
                cluster=cluster,
            )
            node = factory.make_Node(bmc=pod)
            expected_vms.append(
                factory.make_VirtualMachine(
                    machine=node,
                    memory=1024,
                    pinned_cores=[0, 2],
                    hugepages_backed=False,
                    bmc=pod,
                )
            )

        self.assertCountEqual(cluster.virtual_machines(), expected_vms)

    def test_virtual_machines_hosts_no_vms(self):
        cluster_name = factory.make_name("name")
        project = factory.make_name("project")
        cluster = VMCluster(name=cluster_name, project=project)
        for _ in range(0, 3):
            pod = factory.make_Pod(
                pod_type="lxd",
                host=None,
                cores=8,
                memory=4096,
                cluster=cluster,
            )
            factory.make_Node(bmc=pod)
        self.assertEqual(list(cluster.virtual_machines()), [])

    def test_virtual_machines_no_hosts(self):
        cluster_name = factory.make_name("name")
        project = factory.make_name("project")
        cluster = VMCluster(name=cluster_name, project=project)
        self.assertEqual(list(cluster.virtual_machines()), [])
