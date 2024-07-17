# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random
from unittest.mock import Mock
from urllib.parse import urlparse

from twisted.internet.defer import succeed

from maasserver import vmhost as vmhost_module
from maasserver.enum import BMC_TYPE
from maasserver.exceptions import PodProblem
from maasserver.models import NodeKey, Pod, PodHints, VMCluster
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import reload_object
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from provisioningserver.drivers.pod import (
    DiscoveredCluster,
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodStoragePool,
)
from provisioningserver.rpc.cluster import SendPodCommissioningResults


def make_pod_info():
    pod_ip_adddress = factory.make_ipv4_address()
    pod_power_address = "qemu+ssh://user@%s/system" % pod_ip_adddress
    return {
        "type": "virsh",
        "power_address": pod_power_address,
        "ip_address": pod_ip_adddress,
    }


def make_lxd_pod_info(url=None):
    if url is None:
        url = factory.make_ipv4_address() + ":8443"
    return {
        "type": "lxd",
        "power_address": url,
    }


def fake_pod_discovery(testcase):
    discovered_pod = DiscoveredPod(
        architectures=["amd64/generic"],
        cores=random.randint(2, 4),
        memory=random.randint(2048, 4096),
        local_storage=random.randint(1024, 1024 * 1024),
        cpu_speed=random.randint(2048, 4048),
        hints=DiscoveredPodHints(
            cores=random.randint(2, 4),
            memory=random.randint(1024, 4096),
            local_storage=random.randint(1024, 1024 * 1024),
            cpu_speed=random.randint(2048, 4048),
        ),
        storage_pools=[
            DiscoveredPodStoragePool(
                id=factory.make_name("pool_id"),
                name=factory.make_name("name"),
                type=factory.make_name("type"),
                path="/var/lib/path/%s" % factory.make_name("path"),
                storage=random.randint(1024, 1024 * 1024),
            )
            for _ in range(3)
        ],
    )
    discovered_rack_1 = factory.make_RackController()
    discovered_rack_2 = factory.make_RackController()
    failed_rack = factory.make_RackController()
    testcase.patch(vmhost_module, "post_commit_do")
    testcase.patch(vmhost_module, "discover_pod").return_value = (
        {
            discovered_rack_1.system_id: discovered_pod,
            discovered_rack_2.system_id: discovered_pod,
        },
        {failed_rack.system_id: factory.make_exception()},
    )
    return (
        discovered_pod,
        [discovered_rack_1, discovered_rack_2],
        [failed_rack],
    )


def fake_cluster_discovery(testcase):
    discovered_cluster = DiscoveredCluster(
        name=factory.make_name("cluster"),
        project=factory.make_name("project"),
        pods=[
            DiscoveredPod(
                name=factory.make_name("pod"),
                architectures=["amd64/generic"],
                cores=random.randint(2, 4),
                memory=random.randint(2048, 4096),
                local_storage=random.randint(1024, 1024 * 1024),
                cpu_speed=random.randint(2048, 4048),
                hints=DiscoveredPodHints(
                    cores=random.randint(2, 4),
                    memory=random.randint(1024, 4096),
                    local_storage=random.randint(1024, 1024 * 1024),
                    cpu_speed=random.randint(2048, 4048),
                ),
                storage_pools=[
                    DiscoveredPodStoragePool(
                        id=factory.make_name("pool_id"),
                        name=factory.make_name("name"),
                        type=factory.make_name("type"),
                        path="/var/lib/path/%s" % factory.make_name("path"),
                        storage=random.randint(1024, 1024 * 1024),
                    )
                    for _ in range(3)
                ],
                clustered=True,
            )
            for _ in range(3)
        ],
        pod_addresses=["https://lxd-%d" % i for i in range(3)],
    )
    discovered_rack_1 = factory.make_RackController()
    discovered_rack_2 = factory.make_RackController()
    failed_rack = factory.make_RackController()
    testcase.patch(vmhost_module, "post_commit_do")
    testcase.patch(vmhost_module, "discover_pod").return_value = (
        {
            discovered_rack_1.system_id: discovered_cluster.pods[0],
            discovered_rack_2.system_id: discovered_cluster.pods[0],
        },
        {failed_rack.system_id: factory.make_exception()},
    )
    return (
        discovered_cluster,
        [discovered_rack_1, discovered_rack_2],
        [failed_rack],
    )


class TestDiscoverAndSyncVMHost(MAASServerTestCase):
    def test_sync_details(self):
        (
            discovered_pod,
            discovered_racks,
            failed_racks,
        ) = fake_pod_discovery(self)
        zone = factory.make_Zone()
        pod_info = make_pod_info()
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = factory.make_Pod(
            zone=zone, pod_type=pod_info["type"], parameters=power_parameters
        )
        vmhost = vmhost_module.discover_and_sync_vmhost(
            orig_vmhost, factory.make_User()
        )
        self.assertEqual(vmhost.id, orig_vmhost.id)
        self.assertEqual(vmhost.bmc_type, BMC_TYPE.POD)
        self.assertEqual(vmhost.architectures, ["amd64/generic"])
        self.assertEqual(vmhost.name, orig_vmhost.name)
        self.assertEqual(vmhost.cores, discovered_pod.cores)
        self.assertEqual(vmhost.memory, discovered_pod.memory)
        self.assertEqual(vmhost.cpu_speed, discovered_pod.cpu_speed)
        self.assertEqual(vmhost.zone, zone)
        self.assertEqual(vmhost.power_type, "virsh")
        self.assertEqual(vmhost.get_power_parameters(), power_parameters)
        self.assertEqual(vmhost.ip_address.ip, pod_info["ip_address"])
        routable_racks = [
            relation.rack_controller
            for relation in vmhost.routable_rack_relationships.all()
            if relation.routable
        ]
        not_routable_racks = [
            relation.rack_controller
            for relation in vmhost.routable_rack_relationships.all()
            if not relation.routable
        ]
        self.assertCountEqual(routable_racks, discovered_racks)
        self.assertCountEqual(not_routable_racks, failed_racks)

    def test_raises_exception_from_rack_controller(self):
        failed_rack = factory.make_RackController()
        exc = factory.make_exception()
        self.patch(vmhost_module, "discover_pod").return_value = (
            {},
            {failed_rack.system_id: exc},
        )
        pod_info = make_pod_info()
        power_parameters = {"power_address": pod_info["power_address"]}
        vmhost = factory.make_Pod(
            pod_type=pod_info["type"],
            parameters=power_parameters,
        )
        error = self.assertRaises(
            PodProblem,
            vmhost_module.discover_and_sync_vmhost,
            vmhost,
            factory.make_User(),
        )
        self.assertEqual(str(exc), str(error))
        self.assertIs(error.__cause__, exc)


class TestDiscoverAndSyncVMHostAsync(MAASTransactionServerTestCase):
    wait_for_reactor = wait_for()

    @wait_for_reactor
    async def test_sync_details(self):
        discovered_pod, discovered_racks, failed_racks = await deferToDatabase(
            fake_pod_discovery, self
        )
        vmhost_module.discover_pod.return_value = succeed(
            vmhost_module.discover_pod.return_value
        )
        zone = await deferToDatabase(factory.make_Zone)
        pod_info = await deferToDatabase(make_pod_info)
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = await deferToDatabase(
            factory.make_Pod,
            zone=zone,
            pod_type=pod_info["type"],
            parameters=power_parameters,
        )
        user = await deferToDatabase(factory.make_User)
        vmhost = await vmhost_module.discover_and_sync_vmhost_async(
            orig_vmhost, user
        )
        vmhost_power_parameters = await deferToDatabase(
            vmhost.get_power_parameters
        )
        self.assertEqual(vmhost.id, orig_vmhost.id)
        self.assertEqual(vmhost.bmc_type, BMC_TYPE.POD)
        self.assertEqual(vmhost.architectures, ["amd64/generic"])
        self.assertEqual(vmhost.name, orig_vmhost.name)
        self.assertEqual(vmhost.cores, discovered_pod.cores)
        self.assertEqual(vmhost.memory, discovered_pod.memory)
        self.assertEqual(vmhost.cpu_speed, discovered_pod.cpu_speed)
        self.assertEqual(vmhost.zone, zone)
        self.assertEqual(vmhost.power_type, "virsh")
        self.assertEqual(vmhost_power_parameters, power_parameters)
        self.assertEqual(vmhost.ip_address.ip, pod_info["ip_address"])

        def validate_rack_routes():
            routable_racks = [
                relation.rack_controller
                for relation in vmhost.routable_rack_relationships.all()
                if relation.routable
            ]
            not_routable_racks = [
                relation.rack_controller
                for relation in vmhost.routable_rack_relationships.all()
                if not relation.routable
            ]
            self.assertCountEqual(routable_racks, discovered_racks)
            self.assertCountEqual(not_routable_racks, failed_racks)

        await deferToDatabase(validate_rack_routes)

    @wait_for_reactor
    async def test_raises_exception_from_rack_controller(self):
        failed_rack = await deferToDatabase(factory.make_RackController)
        exc = factory.make_exception()
        self.patch(vmhost_module, "discover_pod").return_value = succeed(
            ({}, {failed_rack.system_id: exc})
        )
        pod_info = await deferToDatabase(make_pod_info)
        power_parameters = {"power_address": pod_info["power_address"]}
        vmhost = yield deferToDatabase(
            factory.make_Pod,
            pod_type=pod_info["type"],
            parameters=power_parameters,
        )
        user = await deferToDatabase(factory.make_User)
        try:
            await vmhost_module.discover_and_sync_vmhost_async(vmhost, user)
        except Exception as error:
            self.assertIsInstance(error, PodProblem)
            self.assertEqual(str(exc), str(error))
            self.assertIs(error.__cause__, exc)
        else:
            self.fail("No exception raised")


class TestCleanPowerAddress(MAASServerTestCase):
    def test_clean_power_address(self):
        cases = [
            ("10.0.0.1", "10.0.0.1:8443"),
            ("10.0.0.1:8443", "10.0.0.1:8443"),
            ("2001:db8::1", "[2001:db8::1]:8443"),
            ("[2001:db8::1]", "[2001:db8::1]:8443"),
            ("lxd-1", "lxd-1:8443"),
            ("lxd.cluster.com", "lxd.cluster.com:8443"),
            ("https://lxd-1", "lxd-1:8443"),
            ("https://lxd-1:8080", "lxd-1:8080"),
            ("https://[2001:db8::1]", "[2001:db8::1]:8443"),
            ("https://[2001:db8::1]:8080", "[2001:db8::1]:8080"),
            ("qemu+ssh://10.0.0.1/system", "qemu+ssh://10.0.0.1/system"),
            (
                "qemu+ssh://10.0.0.1:2200/system",
                "qemu+ssh://10.0.0.1:2200/system",
            ),
        ]
        for case, output in cases:
            ret = vmhost_module._clean_power_address(case)
            self.assertEqual(output, ret)


class TestSyncVMCluster(MAASServerTestCase):
    def test_sync_vmcluster_creates_cluster(self):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = fake_cluster_discovery(self)
        zone = factory.make_Zone()
        pod_info = make_lxd_pod_info(url=discovered_cluster.pod_addresses[0])
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = factory.make_Pod(
            zone=zone, pod_type=pod_info["type"], parameters=power_parameters
        )
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        self.patch(vmhost_module, "discover_pod").return_value = (
            successes,
            failures,
        )
        vmhost = vmhost_module.discover_and_sync_vmhost(
            orig_vmhost, factory.make_User()
        )
        self.assertEqual(vmhost.hints.cluster.name, discovered_cluster.name)
        self.assertEqual(
            vmhost.hints.cluster.project, discovered_cluster.project
        )

    def test_sync_vmcluster_creates_additional_pods(self):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = fake_cluster_discovery(self)
        zone = factory.make_Zone()
        pod_info = make_lxd_pod_info(url=discovered_cluster.pod_addresses[0])
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = factory.make_Pod(
            zone=zone, pod_type=pod_info["type"], parameters=power_parameters
        )
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        self.patch(vmhost_module, "discover_pod").return_value = (
            successes,
            failures,
        )
        vmhost = vmhost_module.discover_and_sync_vmhost(
            orig_vmhost, factory.make_User()
        )
        hints = PodHints.objects.filter(cluster=vmhost.hints.cluster)
        pod_names = [hint.pod.name for hint in hints]
        expected_names = [pod.name for pod in discovered_cluster.pods]
        self.assertCountEqual(pod_names, expected_names)

    def test_sync_vmcluster_adds_host_only_once(self):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = fake_cluster_discovery(self)
        zone = factory.make_Zone()
        pod_info = make_lxd_pod_info(url=discovered_cluster.pod_addresses[0])
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = factory.make_Pod(
            zone=zone, pod_type=pod_info["type"], parameters=power_parameters
        )
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        self.patch(vmhost_module, "discover_pod").return_value = (
            successes,
            failures,
        )
        vmhost = vmhost_module.discover_and_sync_vmhost(
            orig_vmhost, factory.make_User()
        )
        hints = PodHints.objects.filter(cluster=vmhost.hints.cluster)
        pod_names = [hint.pod.name for hint in hints]
        expected_names = [pod.name for pod in discovered_cluster.pods]
        self.assertCountEqual(pod_names, expected_names)

    def test_discovered_vmhosts_receive_correct_tags(self):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = fake_cluster_discovery(self)
        zone = factory.make_Zone()
        pod_info = make_lxd_pod_info(url=discovered_cluster.pod_addresses[0])
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = factory.make_Pod(
            zone=zone, pod_type=pod_info["type"], parameters=power_parameters
        )
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        self.patch(vmhost_module, "discover_pod").return_value = (
            successes,
            failures,
        )
        vmhost = vmhost_module.discover_and_sync_vmhost(
            orig_vmhost, factory.make_User()
        )
        hosts = vmhost.hints.cluster.hosts()
        for host in hosts:
            self.assertIn("pod-console-logging", host.tags)

    def test_discovered_vmhosts_doesnt_update_console_logging_tag_if_exists(
        self,
    ):
        tag = factory.make_Tag(
            name="pod-console-logging", kernel_opts="foo bar"
        )
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = fake_cluster_discovery(self)
        zone = factory.make_Zone()
        pod_info = make_lxd_pod_info(url=discovered_cluster.pod_addresses[0])
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = factory.make_Pod(
            zone=zone, pod_type=pod_info["type"], parameters=power_parameters
        )
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        self.patch(vmhost_module, "discover_pod").return_value = (
            successes,
            failures,
        )
        vmhost = vmhost_module.discover_and_sync_vmhost(
            orig_vmhost, factory.make_User()
        )
        hosts = vmhost.hints.cluster.hosts()
        for host in hosts:
            self.assertIn("pod-console-logging", host.tags)
        tag = reload_object(tag)
        self.assertEqual(tag.kernel_opts, "foo bar")

    def test_sync_vmcluster_adds_vmhost_zone_and_pool(self):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = fake_cluster_discovery(self)
        zone = factory.make_Zone()
        pod_info = make_lxd_pod_info(url=discovered_cluster.pod_addresses[0])
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = factory.make_Pod(
            zone=zone, pod_type=pod_info["type"], parameters=power_parameters
        )
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        self.patch(vmhost_module, "discover_pod").return_value = (
            successes,
            failures,
        )
        vmhost = vmhost_module.discover_and_sync_vmhost(
            orig_vmhost, factory.make_User()
        )
        cluster = VMCluster.objects.get(id=vmhost.hints.cluster_id)
        self.assertEqual(vmhost.pool, cluster.pool)
        self.assertEqual(vmhost.zone, cluster.zone)

    def test_sync_vmcluster_cluster_already_exists(self):
        (
            discovered_cluster,
            _,
            _,
        ) = fake_cluster_discovery(self)
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        cluster = factory.make_VMCluster(
            name=discovered_cluster.name,
            project=discovered_cluster.project,
            zone=zone,
            pool=pool,
            pods=0,
        )
        vmhosts = [
            factory.make_Pod(
                zone=zone,
                pool=pool,
                cluster=cluster,
                name=pod.name,
                pod_type="lxd",
                parameters={
                    "power_address": discovered_cluster.pod_addresses[i]
                },
            )
            for i, pod in enumerate(discovered_cluster.pods)
        ]
        updated_vmhost = vmhost_module.sync_vmcluster(
            discovered_cluster,
            ({"cluster": discovered_cluster},),
            vmhosts[0],
            factory.make_admin(),
        )
        self.assertEqual(updated_vmhost.name, vmhosts[0].name)
        self.assertCountEqual(
            cluster.hosts(), updated_vmhost.hints.cluster.hosts()
        )

    def test_sync_vmcluster_uses_existing_cluster_name_when_exists(
        self,
    ):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = fake_cluster_discovery(self)
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        cluster = factory.make_VMCluster(
            name=factory.make_name("cluster"),
            project=discovered_cluster.project,
            zone=zone,
            pool=pool,
            pods=0,
        )
        vmhosts = [
            factory.make_Pod(
                cluster=cluster,
                parameters={"power_address": address},
                zone=zone,
                pool=pool,
                pod_type="lxd",
            )
            for address in discovered_cluster.pod_addresses
        ]
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        self.patch(vmhost_module, "discover_pod").return_value = (
            successes,
            failures,
        )
        updated_vmhost = vmhost_module.discover_and_sync_vmhost(
            vmhosts[0], factory.make_User()
        )
        self.assertEqual(updated_vmhost.hints.cluster.name, cluster.name)

    def test_sync_vmcluster_uses_vmhost_name_when_no_existing_cluster_or_discovered_cluster_name(
        self,
    ):
        (
            discovered_cluster,
            _,
            _,
        ) = fake_cluster_discovery(self)
        discovered_cluster.name = None
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        vmhost = factory.make_Pod(
            name=discovered_cluster.pods[0].name,
            zone=zone,
            pool=pool,
            pod_type="lxd",
            parameters={"power_address": discovered_cluster.pod_addresses[0]},
        )
        updated_vmhost = vmhost_module.sync_vmcluster(
            discovered_cluster,
            ({"cluster": discovered_cluster},),
            vmhost,
            factory.make_admin(),
        )
        self.assertEqual(vmhost.name, updated_vmhost.cluster.name)

    def test_sync_vmcluster_does_not_duplicate_cluster_or_hosts_on_refresh(
        self,
    ):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = fake_cluster_discovery(self)
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        cluster = factory.make_VMCluster(
            name=factory.make_name("cluster"),
            project=discovered_cluster.project,
            zone=zone,
            pool=pool,
            pods=0,
        )
        vmhosts = [
            factory.make_Pod(
                cluster=cluster,
                parameters={"power_address": address},
                zone=zone,
                pool=pool,
                pod_type="lxd",
            )
            for i, address in enumerate(discovered_cluster.pod_addresses)
        ]
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        self.patch(vmhost_module, "discover_pod").return_value = (
            successes,
            failures,
        )
        discovered_cluster.name = factory.make_name("new_cluster_name")
        updated_vmhost = vmhost_module.discover_and_sync_vmhost(
            vmhosts[0], factory.make_User()
        )
        self.assertEqual(updated_vmhost.cluster.name, cluster.name)
        hosts = Pod.objects.filter(
            name__in=[vmhost.name for vmhost in vmhosts]
        )
        self.assertEqual(len(vmhosts), len(hosts))
        self.assertEqual(updated_vmhost.cluster.id, cluster.id)

    def test_sync_vmcluster_return_correct_pod_on_refresh(
        self,
    ):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = fake_cluster_discovery(self)
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        cluster = factory.make_VMCluster(
            name=factory.make_name("cluster"),
            project=discovered_cluster.project,
            zone=zone,
            pool=pool,
            pods=0,
        )
        vmhosts = [
            factory.make_Pod(
                cluster=cluster,
                parameters={"power_address": address},
                zone=zone,
                pool=pool,
                pod_type="lxd",
                name=discovered_cluster.pods[i].name,
            )
            for i, address in enumerate(discovered_cluster.pod_addresses)
        ]
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        self.patch(vmhost_module, "discover_pod").return_value = (
            successes,
            failures,
        )
        updated_vmhost = vmhost_module.discover_and_sync_vmhost(
            vmhosts[1], factory.make_User()
        )
        self.assertEqual(updated_vmhost.id, vmhosts[1].id)
        self.assertEqual(updated_vmhost.name, vmhosts[1].name)
        hosts = Pod.objects.filter(
            name__in=[vmhost.name for vmhost in vmhosts]
        )
        self.assertEqual(len(vmhosts), len(hosts))
        self.assertEqual(updated_vmhost.cluster.id, cluster.id)


class TestSyncVMClusterAsync(MAASTransactionServerTestCase):
    wait_for_reactor = wait_for()

    @wait_for_reactor
    async def test_sync_vmcluster_async_creates_cluster(self):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = await deferToDatabase(fake_cluster_discovery, self)
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        vmhost_module.discover_pod.return_value = succeed(
            (successes, failures)
        )
        zone = await deferToDatabase(factory.make_Zone)
        pod_info = await deferToDatabase(make_lxd_pod_info)
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = await deferToDatabase(
            factory.make_Pod,
            zone=zone,
            pod_type=pod_info["type"],
            parameters=power_parameters,
        )
        user = await deferToDatabase(factory.make_User)
        vmhost = await vmhost_module.discover_and_sync_vmhost_async(
            orig_vmhost, user
        )
        self.assertEqual(vmhost.hints.cluster.name, discovered_cluster.name)
        self.assertEqual(
            vmhost.hints.cluster.project, discovered_cluster.project
        )

    @wait_for_reactor
    async def test_sync_vmcluster_async_creates_additional(self):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = await deferToDatabase(fake_cluster_discovery, self)
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        vmhost_module.discover_pod.return_value = succeed(
            (successes, failures)
        )
        zone = await deferToDatabase(factory.make_Zone)
        pod_info = await deferToDatabase(make_lxd_pod_info)
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = await deferToDatabase(
            factory.make_Pod,
            zone=zone,
            pod_type=pod_info["type"],
            parameters=power_parameters,
        )
        user = await deferToDatabase(factory.make_User)
        vmhost = await vmhost_module.discover_and_sync_vmhost_async(
            orig_vmhost, user
        )

        def _get_cluster_pod_names():
            hints = PodHints.objects.filter(cluster=vmhost.hints.cluster)
            return [hint.pod.name for hint in hints]

        pod_names = await deferToDatabase(_get_cluster_pod_names)
        expected_names = [pod.name for pod in discovered_cluster.pods]
        self.assertCountEqual(pod_names, expected_names)

    @wait_for_reactor
    async def test_sync_vmcluster_async_cluster_has_vmhost_pool_and_zone(self):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = await deferToDatabase(fake_cluster_discovery, self)
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        vmhost_module.discover_pod.return_value = succeed(
            (successes, failures)
        )
        zone = await deferToDatabase(factory.make_Zone)
        pod_info = await deferToDatabase(make_lxd_pod_info)
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = await deferToDatabase(
            factory.make_Pod,
            zone=zone,
            pod_type=pod_info["type"],
            parameters=power_parameters,
        )
        user = await deferToDatabase(factory.make_User)
        vmhost = await vmhost_module.discover_and_sync_vmhost_async(
            orig_vmhost, user
        )

        def _check_cluster():
            cluster = VMCluster.objects.get(id=vmhost.hints.cluster_id)
            self.assertEqual(vmhost.pool, cluster.pool)
            self.assertEqual(vmhost.zone, cluster.zone)

        await deferToDatabase(_check_cluster)

    @wait_for_reactor
    async def test_discovered_vmhosts_receive_correct_tags_async(self):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = await deferToDatabase(fake_cluster_discovery, self)
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        vmhost_module.discover_pod.return_value = succeed(
            (successes, failures)
        )
        zone = await deferToDatabase(factory.make_Zone)
        pod_info = await deferToDatabase(make_lxd_pod_info)
        power_parameters = {"power_address": pod_info["power_address"]}
        orig_vmhost = await deferToDatabase(
            factory.make_Pod,
            zone=zone,
            pod_type=pod_info["type"],
            parameters=power_parameters,
        )
        user = await deferToDatabase(factory.make_User)
        vmhost = await vmhost_module.discover_and_sync_vmhost_async(
            orig_vmhost, user
        )

        def _get_vmhosts_tags():
            hosts = vmhost.hints.cluster.hosts()
            return [tag for host in hosts for tag in host.tags]

        tags = await deferToDatabase(_get_vmhosts_tags)
        for tag in tags:
            self.assertEqual("pod-console-logging", tag)

    @wait_for_reactor
    async def test_sync_vmcluster_async_cluster_already_exists(self):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = await deferToDatabase(fake_cluster_discovery, self)
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        vmhost_module.discover_pod.return_value = succeed(
            (successes, failures)
        )
        zone = await deferToDatabase(factory.make_Zone)
        pool = await deferToDatabase(factory.make_ResourcePool)
        cluster = await deferToDatabase(
            factory.make_VMCluster,
            name=discovered_cluster.name,
            project=discovered_cluster.project,
            zone=zone,
            pool=pool,
            pods=0,
        )
        vmhosts = [
            await deferToDatabase(
                factory.make_Pod,
                zone=zone,
                pool=pool,
                cluster=cluster,
                name=pod.name,
                pod_type="lxd",
                parameters={
                    "power_address": discovered_cluster.pod_addresses[i]
                },
            )
            for i, pod in enumerate(discovered_cluster.pods)
        ]
        admin = await deferToDatabase(factory.make_admin)
        updated_vmhost = await vmhost_module.sync_vmcluster_async(
            discovered_cluster,
            ({"cluster": discovered_cluster},),
            vmhosts[0],
            admin,
        )
        self.assertEqual(updated_vmhost.name, vmhosts[0].name)

        def _compare_cluster():
            self.assertCountEqual(
                cluster.hosts(), updated_vmhost.hints.cluster.hosts()
            )

        await deferToDatabase(_compare_cluster)

    @wait_for_reactor
    async def test_sync_vmcluster_uses_existing_cluster_name_when_discovered_cluster_has_none_async(
        self,
    ):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = await deferToDatabase(fake_cluster_discovery, self)
        discovered_cluster.name = None
        zone = await deferToDatabase(factory.make_Zone)
        pool = await deferToDatabase(factory.make_ResourcePool)
        cluster = await deferToDatabase(
            factory.make_VMCluster,
            name=factory.make_name("cluster"),
            project=discovered_cluster.project,
            zone=zone,
            pool=pool,
            pods=0,
        )

        def _create_vmhosts():
            return [
                factory.make_Pod(
                    cluster=cluster,
                    parameters={"power_address": address},
                    zone=zone,
                    pool=pool,
                    pod_type="lxd",
                )
                for address in discovered_cluster.pod_addresses
            ]

        vmhosts = await deferToDatabase(_create_vmhosts)
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        vmhost_module.discover_pod.return_value = succeed(
            (successes, failures)
        )
        user = await deferToDatabase(factory.make_User)
        updated_vmhost = await vmhost_module.discover_and_sync_vmhost_async(
            vmhosts[0], user
        )

        def _get_name():
            return updated_vmhost.hints.cluster.name

        name = await deferToDatabase(_get_name)
        self.assertEqual(name, cluster.name)

    @wait_for_reactor
    async def test_sync_vmcluster_uses_vmhost_name_when_no_existing_cluster_or_discovered_cluster_name(
        self,
    ):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = await deferToDatabase(fake_cluster_discovery, self)
        discovered_cluster.name = None
        zone = await deferToDatabase(factory.make_Zone)
        pool = await deferToDatabase(factory.make_ResourcePool)
        vmhost = await deferToDatabase(
            factory.make_Pod,
            zone=zone,
            pool=pool,
            pod_type="lxd",
        )
        successes = {
            rack_id: discovered_cluster for rack_id in discovered_racks
        }
        failures = {
            rack_id: factory.make_exception() for rack_id in failed_racks
        }
        self.patch(vmhost_module, "discover_pod").return_value = (
            successes,
            failures,
        )
        admin = await deferToDatabase(factory.make_admin)
        updated_vmhost = await vmhost_module.sync_vmcluster_async(
            discovered_cluster,
            ({"cluster": discovered_cluster},),
            vmhost,
            admin,
        )
        self.assertEqual(vmhost.name, updated_vmhost.cluster.name)

    @wait_for_reactor
    async def test_sync_vmcluster_does_not_duplicate_cluster_or_hosts_on_refresh(
        self,
    ):
        (
            discovered_cluster,
            discovered_racks,
            failed_racks,
        ) = await deferToDatabase(fake_cluster_discovery, self)
        zone = await deferToDatabase(factory.make_Zone)
        pool = await deferToDatabase(factory.make_ResourcePool)
        cluster = await deferToDatabase(
            factory.make_VMCluster,
            name=factory.make_name("cluster"),
            project=discovered_cluster.project,
            zone=zone,
            pool=pool,
            pods=0,
        )

        def make_vmhosts():
            return [
                factory.make_Pod(
                    cluster=cluster,
                    parameters={"power_address": address},
                    zone=zone,
                    pool=pool,
                    pod_type="lxd",
                )
                for address in discovered_cluster.pod_addresses
            ]

        vmhosts = await deferToDatabase(make_vmhosts)

        discovered_cluster.name = factory.make_name("new_cluster_name")
        admin = await deferToDatabase(factory.make_admin)
        updated_vmhost = await vmhost_module.sync_vmcluster_async(
            discovered_cluster,
            ({"cluster": discovered_cluster},),
            vmhosts[1],
            admin,
        )

        def get_updated_cluster():
            return updated_vmhost.cluster

        updated_cluster = await deferToDatabase(get_updated_cluster)
        self.assertEqual(updated_cluster.name, cluster.name)

        def get_new_len():
            return len(
                Pod.objects.filter(
                    name__in=[vmhost.name for vmhost in vmhosts]
                )
            )

        new_len = await deferToDatabase(get_new_len)

        self.assertEqual(len(vmhosts), new_len)
        self.assertEqual(updated_cluster.id, cluster.id)


class TestRequestCommissioningResults(MAASTransactionServerTestCase):
    wait_for_reactor = wait_for()

    @wait_for_reactor
    async def test_request_commissioning_results_call(self):
        client = Mock()
        client.return_value = succeed(None)
        self.patch(vmhost_module, "getClientFromIdentifiers").return_value = (
            client
        )
        machine = await deferToDatabase(factory.make_Machine)
        pod = await deferToDatabase(factory.make_Pod, host=machine)
        power_params = await deferToDatabase(pod.get_power_parameters)
        token = await deferToDatabase(
            NodeKey.objects.get_token_for_node, machine
        )
        await vmhost_module.request_commissioning_results(pod)
        client.assert_called_once_with(
            SendPodCommissioningResults,
            pod_id=pod.id,
            name=pod.name,
            type=pod.power_type,
            system_id=machine.system_id,
            context=power_params,
            consumer_key=token.consumer.key,
            token_key=token.key,
            token_secret=token.secret,
            metadata_url=urlparse(
                "http://localhost:5240/MAAS/metadata/latest/"
            ),
        )
