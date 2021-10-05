# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random
from unittest.mock import MagicMock

from testtools.matchers import Equals
from twisted.internet.defer import succeed
from twisted.internet.threads import deferToThread

from maasserver import vmhost
from maasserver.enum import INTERFACE_TYPE
from maasserver.forms import pods
from maasserver.models import Pod, PodStoragePool
from maasserver.models.virtualmachine import MB, VirtualMachineInterface
from maasserver.rpc.testing.fixtures import MockLiveRegionToClusterRPCFixture
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import DATETIME_FORMAT
from maasserver.websockets.handlers import pod as pod_module
from maasserver.websockets.handlers.pod import ComposeMachineForm, PodHandler
from maastesting.crochet import wait_for
from provisioningserver.certificates import Certificate
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodProject,
    InterfaceAttachType,
)
from provisioningserver.rpc.cluster import DiscoverPodProjects

SAMPLE_CERTIFICATE = Certificate.generate("maas")

wait_for_reactor = wait_for(30)  # 30 seconds.


class TestPodHandler(MAASTransactionServerTestCase):
    def make_pod_info(self):
        # Use virsh pod type as the required fields are specific to the
        # type of pod being created.
        pod_type = "virsh"
        pod_ip_adddress = factory.make_ipv4_address()
        pod_power_address = "qemu+ssh://user@%s/system" % pod_ip_adddress
        pod_password = factory.make_name("password")
        pod_tags = [factory.make_name("tag") for _ in range(3)]
        pod_cpu_over_commit_ratio = random.randint(0, 10)
        pod_memory_over_commit_ratio = random.randint(0, 10)
        return {
            "type": pod_type,
            "power_address": pod_power_address,
            "power_pass": pod_password,
            "ip_address": pod_ip_adddress,
            "tags": pod_tags,
            "cpu_over_commit_ratio": pod_cpu_over_commit_ratio,
            "memory_over_commit_ratio": pod_memory_over_commit_ratio,
        }

    def fake_pod_discovery(self):
        discovered_pod = DiscoveredPod(
            architectures=["amd64/generic"],
            cores=random.randint(2, 4),
            memory=random.randint(1024, 4096),
            local_storage=random.randint(1024, 1024 * 1024),
            cpu_speed=random.randint(2048, 4048),
            hints=DiscoveredPodHints(
                cores=random.randint(2, 4),
                memory=random.randint(1024, 4096),
                local_storage=random.randint(1024, 1024 * 1024),
                cpu_speed=random.randint(2048, 4048),
            ),
        )
        discovered_rack_1 = factory.make_RackController()
        discovered_rack_2 = factory.make_RackController()
        failed_rack = factory.make_RackController()
        self.patch(vmhost, "discover_pod").return_value = succeed(
            (
                {
                    discovered_rack_1.system_id: discovered_pod,
                    discovered_rack_2.system_id: discovered_pod,
                },
                {failed_rack.system_id: factory.make_exception()},
            )
        )

    def make_pod_with_hints(self, **kwargs):
        architectures = [
            "amd64/generic",
            "i386/generic",
            "arm64/generic",
            "armhf/generic",
        ]
        pod = factory.make_Pod(
            architectures=architectures,
            capabilities=[
                Capabilities.COMPOSABLE,
                Capabilities.STORAGE_POOLS,
            ],
            **kwargs,
        )
        pod.hints.cores = random.randint(8, 16)
        pod.hints.memory = random.randint(4096, 8192)
        pod.hints.cpu_speed = random.randint(2000, 3000)
        pod.hints.save()
        for _ in range(3):
            pool = factory.make_PodStoragePool(pod)
        pod.default_storage_pool = pool
        pod.save()
        return pod

    def test_allowed_methods(self):
        handler = PodHandler(factory.make_admin(), {}, None)
        self.assertCountEqual(
            handler.Meta.allowed_methods,
            [
                "list",
                "get",
                "create",
                "update",
                "delete",
                "set_active",
                "refresh",
                "compose",
                "get_projects",
            ],
        )

    def test_get(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        power_params = {
            "power_address": "1.2.3.4",
            "certificate": SAMPLE_CERTIFICATE.certificate_pem(),
            "key": SAMPLE_CERTIFICATE.private_key_pem(),
            "project": "maas",
        }
        pod = self.make_pod_with_hints(
            pod_type="lxd",
            parameters=power_params,
        )
        # Create machines to test owners_count
        factory.make_Node()
        factory.make_Node(bmc=pod)
        factory.make_Node(bmc=pod, owner=admin)
        factory.make_Node(bmc=pod, owner=factory.make_User())
        expected_data = handler.full_dehydrate(pod)
        result = handler.get({"id": pod.id})
        self.assertEqual(expected_data.keys(), result.keys())
        for key in expected_data:
            self.assertEqual(expected_data[key], result[key], key)
        self.assertEqual(result, expected_data)
        self.assertIsNone(result["host"])
        self.assertEqual(result["attached_vlans"], [])
        self.assertEqual(result["boot_vlans"], [])
        self.assertEqual(
            result["storage_pools"], expected_data["storage_pools"]
        )
        self.assertEqual(result["power_parameters"], power_params)

    def test_get_with_pod_host(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        vlan = factory.make_VLAN(dhcp_on=True)
        subnet = factory.make_Subnet(vlan=vlan)
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        ip = factory.make_StaticIPAddress(
            interface=node.boot_interface, subnet=subnet
        )
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 3]
        numa_node0.memory = 4096
        numa_node0.save()
        factory.make_NUMANode(node=node, cores=[1, 4], memory=1024)
        factory.make_NUMANode(node=node, cores=[2, 5], memory=2048)
        project = factory.make_string()
        pod = self.make_pod_with_hints(
            pod_type="lxd",
            parameters={"project": project},
            host=node,
            ip_address=ip,
        )
        vm0 = factory.make_VirtualMachine(
            project=project,
            memory=1024,
            pinned_cores=[0],
            hugepages_backed=False,
            bmc=pod,
            machine=factory.make_Node(system_id="vm0"),
        )
        vm1 = factory.make_VirtualMachine(
            project=project,
            memory=1024,
            pinned_cores=[2, 5],
            hugepages_backed=False,
            bmc=pod,
            machine=factory.make_Node(system_id="vm1"),
        )

        expected_numa_details = [
            {
                "cores": {"allocated": [0], "free": [3]},
                "interfaces": [node.boot_interface.id],
                "memory": {
                    "general": {"allocated": 1024 * MB, "free": 3072 * MB},
                    "hugepages": [],
                },
                "node_id": 0,
                "vms": [vm0.id],
            },
            {
                "cores": {"allocated": [], "free": [1, 4]},
                "interfaces": [],
                "memory": {
                    "general": {"allocated": 0, "free": 1024 * MB},
                    "hugepages": [],
                },
                "node_id": 1,
                "vms": [],
            },
            {
                "cores": {"allocated": [2, 5], "free": []},
                "interfaces": [],
                "memory": {
                    "general": {"allocated": 1024 * MB, "free": 1024 * MB},
                    "hugepages": [],
                },
                "node_id": 2,
                "vms": [vm1.id],
            },
        ]
        result = handler.get({"id": pod.id})
        self.assertThat(result["host"], Equals(node.system_id))
        self.assertThat(result["attached_vlans"], Equals([subnet.vlan_id]))
        self.assertThat(result["boot_vlans"], Equals([subnet.vlan_id]))
        resources = result["resources"]
        self.assertEqual(
            resources["cores"],
            {"allocated_other": 0, "allocated_tracked": 3, "free": 3},
        )
        self.assertEqual(
            resources["interfaces"],
            [
                {
                    "id": node.boot_interface.id,
                    "name": node.boot_interface.name,
                    "numa_index": 0,
                    "virtual_functions": {
                        "allocated_other": 0,
                        "allocated_tracked": 0,
                        "free": 0,
                    },
                }
            ],
        )
        self.assertEqual(
            resources["memory"],
            {
                "general": {
                    "allocated_other": 0,
                    "allocated_tracked": 2147483648,
                    "free": 5368709120,
                },
                "hugepages": {
                    "allocated_other": 0,
                    "allocated_tracked": 0,
                    "free": 0,
                },
            },
        )
        self.assertEqual(resources["numa"], expected_numa_details)
        self.assertEqual(resources["vm_count"], {"other": 0, "tracked": 2})
        self.assertCountEqual(
            resources["vms"],
            [
                {
                    "id": vm0.id,
                    "system_id": "vm0",
                    "memory": 1024 * MB,
                    "hugepages_backed": False,
                    "pinned_cores": [0],
                    "unpinned_cores": 0,
                },
                {
                    "id": vm1.id,
                    "system_id": "vm1",
                    "memory": 1024 * MB,
                    "hugepages_backed": False,
                    "pinned_cores": [2, 5],
                    "unpinned_cores": 0,
                },
            ],
        )

    def test_get_with_pod_host_no_storage_pools(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        node = factory.make_Node()
        pod = self.make_pod_with_hints(
            pod_type="lxd",
            host=node,
        )
        pod.default_storage_pool = None
        pod.save()
        PodStoragePool.objects.all().delete()
        result = handler.get({"id": pod.id})
        self.assertIsNone(result["default_storage_pool"])
        self.assertEqual(result["storage_pools"], [])

    def test_get_with_pod_host_no_vlan(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        node = factory.make_Node()
        pod = self.make_pod_with_hints(
            pod_type="lxd",
            host=node,
        )
        # attach an unconnected interface to the node
        interface = factory.make_Interface(node=node)
        interface.vlan = None
        interface.save()
        result = handler.get({"id": pod.id})
        self.assertEqual(result["attached_vlans"], [])

    def test_get_host_interfaces_no_sriov(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        node = factory.make_Machine()
        numa_node0 = node.default_numanode
        numa_node1 = factory.make_NUMANode(node=node)
        iface1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name="eth0", numa_node=numa_node0
        )
        br1 = factory.make_Interface(
            INTERFACE_TYPE.BRIDGE,
            name="br0",
            numa_node=numa_node0,
            parents=[iface1],
        )
        iface2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, name="eth1", numa_node=numa_node1
        )
        pod = self.make_pod_with_hints(
            pod_type="lxd",
            host=node,
        )
        vm_machine0 = factory.make_Node(system_id="vm0")
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=vm_machine0,
            mac_address="11:11:11:11:11:11",
        )
        vm_machine1 = factory.make_Node(system_id="vm1")
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=vm_machine1,
            mac_address="aa:aa:aa:aa:aa:aa",
        )
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=vm_machine1,
            mac_address="bb:bb:bb:bb:bb:bb",
        )
        vm0 = factory.make_VirtualMachine(
            bmc=pod,
            machine=vm_machine0,
        )
        VirtualMachineInterface.objects.create(
            vm=vm0,
            mac_address="11:11:11:11:11:11",
            host_interface=br1,
            attachment_type=InterfaceAttachType.BRIDGE,
        )
        vm1 = factory.make_VirtualMachine(bmc=pod, machine=vm_machine1)
        VirtualMachineInterface.objects.create(
            vm=vm1,
            mac_address="aa:aa:aa:aa:aa:aa",
            host_interface=br1,
            attachment_type=InterfaceAttachType.BRIDGE,
        )
        VirtualMachineInterface.objects.create(
            vm=vm1,
            mac_address="bb:bb:bb:bb:bb:bb",
            host_interface=iface2,
            attachment_type=InterfaceAttachType.MACVLAN,
        )

        result = handler.get({"id": pod.id})
        numa1, numa2 = result["resources"]["numa"]
        self.assertCountEqual(numa1["interfaces"], [iface1.id, br1.id])
        self.assertCountEqual(numa1["vms"], [vm0.id, vm1.id])
        self.assertCountEqual(numa2["interfaces"], [iface2.id])
        self.assertCountEqual(numa2["vms"], [vm1.id])
        self.assertCountEqual(
            result["resources"]["interfaces"],
            [
                {
                    "id": iface1.id,
                    "name": "eth0",
                    "numa_index": 0,
                    "virtual_functions": {
                        "allocated_tracked": 0,
                        "allocated_other": 0,
                        "free": 0,
                    },
                },
                {
                    "id": br1.id,
                    "name": "br0",
                    "numa_index": 0,
                    "virtual_functions": {
                        "allocated_tracked": 0,
                        "allocated_other": 0,
                        "free": 0,
                    },
                },
                {
                    "id": iface2.id,
                    "name": "eth1",
                    "numa_index": 1,
                    "virtual_functions": {
                        "allocated_tracked": 0,
                        "allocated_other": 0,
                        "free": 0,
                    },
                },
            ],
        )

    def test_get_host_interfaces_sriov(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        node = factory.make_Machine()
        numa_node0 = node.default_numanode
        numa_node1 = factory.make_NUMANode(node=node)
        iface1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth0",
            numa_node=numa_node0,
            sriov_max_vf=8,
        )
        iface2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth1",
            numa_node=numa_node1,
            sriov_max_vf=16,
        )
        pod = self.make_pod_with_hints(
            pod_type="lxd",
            host=node,
        )
        vm_machine0 = factory.make_Node(system_id="vm0")
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=vm_machine0,
            mac_address="11:11:11:11:11:11",
        )
        vm_machine1 = factory.make_Node(system_id="vm1")
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=vm_machine1,
            mac_address="aa:aa:aa:aa:aa:aa",
        )
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            node=vm_machine1,
            mac_address="bb:bb:bb:bb:bb:bb",
        )
        vm0 = factory.make_VirtualMachine(
            bmc=pod,
            machine=vm_machine0,
        )
        VirtualMachineInterface.objects.create(
            vm=vm0,
            mac_address="11:11:11:11:11:11",
            host_interface=iface1,
            attachment_type=InterfaceAttachType.SRIOV,
        )
        vm1 = factory.make_VirtualMachine(bmc=pod, machine=vm_machine1)
        VirtualMachineInterface.objects.create(
            vm=vm1,
            mac_address="aa:aa:aa:aa:aa:aa",
            host_interface=iface1,
            attachment_type=InterfaceAttachType.SRIOV,
        )
        VirtualMachineInterface.objects.create(
            vm=vm1,
            mac_address="bb:bb:bb:bb:bb:bb",
            host_interface=iface2,
            attachment_type=InterfaceAttachType.SRIOV,
        )

        result = handler.get({"id": pod.id})
        numa1, numa2 = result["resources"]["numa"]
        self.assertCountEqual(numa1["interfaces"], [iface1.id])
        self.assertCountEqual(numa2["interfaces"], [iface2.id])
        self.assertCountEqual(
            result["resources"]["interfaces"],
            [
                {
                    "id": iface1.id,
                    "name": "eth0",
                    "numa_index": 0,
                    "virtual_functions": {
                        "allocated_tracked": 2,
                        "allocated_other": 0,
                        "free": 6,
                    },
                },
                {
                    "id": iface2.id,
                    "name": "eth1",
                    "numa_index": 1,
                    "virtual_functions": {
                        "allocated_tracked": 1,
                        "allocated_other": 0,
                        "free": 15,
                    },
                },
            ],
        )

    def test_get_with_pod_host_determines_vlan_boot_status(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        vlan = factory.make_VLAN(dhcp_on=False)
        subnet = factory.make_Subnet(vlan=vlan)
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        ip = factory.make_StaticIPAddress(
            interface=node.boot_interface, subnet=subnet
        )
        pod = self.make_pod_with_hints(ip_address=ip)
        expected_data = handler.full_dehydrate(pod)
        result = handler.get({"id": pod.id})
        self.assertEqual(expected_data.keys(), result.keys())
        for key in expected_data:
            self.assertEqual(expected_data[key], result[key], key)
        self.assertThat(result, Equals(expected_data))
        self.assertThat(result["attached_vlans"], Equals([subnet.vlan_id]))
        self.assertThat(result["boot_vlans"], Equals([]))

    def test_get_with_certificate_info(self):
        pod = self.make_pod_with_hints(
            pod_type="lxd",
            parameters={
                "certificate": SAMPLE_CERTIFICATE.certificate_pem(),
                "key": SAMPLE_CERTIFICATE.private_key_pem(),
            },
        )
        handler = PodHandler(factory.make_User(), {}, None)
        result = handler.get({"id": pod.id})
        self.assertEqual(
            result["certificate"],
            {
                "CN": SAMPLE_CERTIFICATE.cn(),
                "fingerprint": SAMPLE_CERTIFICATE.cert_hash(),
                "expiration": SAMPLE_CERTIFICATE.expiration().strftime(
                    DATETIME_FORMAT
                ),
            },
        )

    def test_get_no_certificate(self):
        pod = self.make_pod_with_hints(
            pod_type="virsh",
            parameters={},
        )
        handler = PodHandler(factory.make_User(), {}, None)
        result = handler.get({"id": pod.id})
        self.assertNotIn("certificate-metadata", result)

    def test_get_as_standard_user(self):
        user = factory.make_User()
        handler = PodHandler(user, {}, None)
        pod = self.make_pod_with_hints()
        expected_data = handler.full_dehydrate(pod)
        result = handler.get({"id": pod.id})
        self.assertThat(result, Equals(expected_data))

    def test_get_permissions(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        pod = self.make_pod_with_hints()
        result = handler.full_dehydrate(pod)
        self.assertEqual(["edit", "delete", "compose"], result["permissions"])

    def test_list(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        pod = self.make_pod_with_hints()
        expected_data = [handler.full_dehydrate(pod, for_list=True)]
        result = handler.list({"id": pod.id})
        self.assertThat(result, Equals(expected_data))

    def test_full_dehydrate_for_list_no_details(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        vlan = factory.make_VLAN(dhcp_on=True)
        subnet = factory.make_Subnet(vlan=vlan)
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        ip = factory.make_StaticIPAddress(
            interface=node.boot_interface, subnet=subnet
        )
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 3]
        numa_node0.memory = 4096
        numa_node0.save()
        factory.make_NUMANode(node=node, cores=[1, 4], memory=1024)
        factory.make_NUMANode(node=node, cores=[2, 5], memory=2048)
        project = factory.make_string()
        pod = self.make_pod_with_hints(
            pod_type="lxd",
            parameters={"project": project},
            host=node,
            ip_address=ip,
        )
        factory.make_VirtualMachine(bmc=pod, project=project)
        result = handler.full_dehydrate(pod, for_list=True)
        self.assertEqual(result["resources"]["numa"], [])
        self.assertEqual(result["resources"]["vms"], [])

    def test_full_dehydrate_for_list_no_cert_metadata(self):
        pod = self.make_pod_with_hints(
            pod_type="lxd",
            parameters={
                "certificate": SAMPLE_CERTIFICATE.certificate_pem(),
                "key": SAMPLE_CERTIFICATE.private_key_pem(),
            },
        )
        handler = PodHandler(factory.make_User(), {}, None)
        result = handler.full_dehydrate(pod, for_list=True)
        self.assertNotIn("certificate-metadata", result)

    def get_rack_rpc_protocol(self, rack_controller, *commands):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())

        fixture = self.useFixture(MockLiveRegionToClusterRPCFixture())
        return fixture.makeCluster(rack_controller, *commands)

    @wait_for_reactor
    async def test_get_projects_with_password(self):
        rack_controller = await deferToDatabase(factory.make_RackController)
        protocol = await deferToThread(
            self.get_rack_rpc_protocol, rack_controller, DiscoverPodProjects
        )
        protocol.DiscoverPodProjects.return_value = succeed(
            {
                "projects": [
                    DiscoveredPodProject(
                        name="foo",
                        description="Project foo",
                    ),
                    DiscoveredPodProject(
                        name="bar",
                        description="Project bar",
                    ),
                ]
            }
        )

        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        params = {
            "type": "lxd",
            "power_address": "1.2.3.4",
            "project": "p1",
            "password": "secret",
            "certificate": "mycert",
            "key": "mykey",
        }
        projects = await handler.execute("get_projects", params)
        self.assertEqual(
            projects,
            [
                {"name": "foo", "description": "Project foo"},
                {"name": "bar", "description": "Project bar"},
            ],
        )
        protocol.DiscoverPodProjects.assert_called_once_with(
            protocol,
            type="lxd",
            context={
                "power_address": "1.2.3.4",
                "project": "p1",
                "password": "secret",
                "certificate": "mycert",
                "key": "mykey",
            },
        )

    @wait_for_reactor
    async def test_get_projects_without_password(self):
        rack_controller = await deferToDatabase(factory.make_RackController)
        protocol = await deferToThread(
            self.get_rack_rpc_protocol, rack_controller, DiscoverPodProjects
        )
        protocol.DiscoverPodProjects.return_value = succeed(
            {
                "projects": [
                    DiscoveredPodProject(
                        name="foo",
                        description="Project foo",
                    ),
                    DiscoveredPodProject(
                        name="bar",
                        description="Project bar",
                    ),
                ]
            }
        )

        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        params = {
            "type": "lxd",
            "power_address": "1.2.3.4",
            "project": "p1",
            "certificate": "mycert",
            "key": "mykey",
        }
        projects = await handler.execute("get_projects", params)
        self.assertEqual(
            projects,
            [
                {"name": "foo", "description": "Project foo"},
                {"name": "bar", "description": "Project bar"},
            ],
        )
        protocol.DiscoverPodProjects.assert_called_once_with(
            protocol,
            type="lxd",
            context={
                "power_address": "1.2.3.4",
                "project": "p1",
                "certificate": "mycert",
                "key": "mykey",
            },
        )

    @wait_for_reactor
    async def test_refresh(self):
        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pod = await deferToDatabase(self.make_pod_with_hints)
        self.patch(
            pod_module, "discover_and_sync_vmhost_async"
        ).return_value = succeed(pod)
        expected_data = await deferToDatabase(
            handler.full_dehydrate, pod, for_list=False
        )
        observed_data = await handler.refresh({"id": pod.id})
        self.assertEqual(expected_data.keys(), observed_data.keys())
        for key in expected_data:
            self.assertEqual(expected_data[key], observed_data[key], key)
        self.assertEqual(expected_data, observed_data)

    @wait_for_reactor
    async def test_delete(self):
        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pod = await deferToDatabase(self.make_pod_with_hints)
        await handler.delete({"id": pod.id})
        expected_pod = await deferToDatabase(reload_object, pod)
        self.assertIsNone(expected_pod)

    @wait_for_reactor
    async def test_delete_decompose(self):
        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pod = await deferToDatabase(self.make_pod_with_hints)
        mock_async_delete = self.patch(Pod, "async_delete")
        mock_async_delete.return_value = succeed(None)
        await deferToDatabase(factory.make_Machine, bmc=pod)
        await handler.delete({"id": pod.id, "decompose": True})
        mock_async_delete.assert_called_once_with(decompose=True)

    @wait_for_reactor
    async def test_create(self):
        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        zone = await deferToDatabase(factory.make_Zone)
        pod_info = self.make_pod_info()
        pod_info["zone"] = zone.id
        await deferToDatabase(self.fake_pod_discovery)
        created_pod = await handler.create(pod_info)
        self.assertIsNotNone(created_pod["id"])

    @wait_for_reactor
    async def test_create_succeeds_with_failed_refresh(self):
        def setup_fakes():
            self.fake_pod_discovery()
            failed_rack = factory.make_RackController()
            self.patch(vmhost, "discover_pod").return_value = (
                {},
                {failed_rack.system_id: factory.make_exception()},
            )

        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        zone = await deferToDatabase(factory.make_Zone)
        pod_info = self.make_pod_info()
        pod_info["zone"] = zone.id
        await deferToDatabase(setup_fakes)
        created_pod = await handler.create(pod_info)
        self.assertIsNotNone(created_pod["id"])

    @wait_for_reactor
    async def test_create_with_pool(self):
        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pool = await deferToDatabase(factory.make_ResourcePool)
        pod_info = self.make_pod_info()
        pod_info["pool"] = pool.id
        await deferToDatabase(self.fake_pod_discovery)
        created_pod = await handler.create(pod_info)
        self.assertEqual(pool.id, created_pod["pool"])

    @wait_for_reactor
    async def test_update(self):
        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        zone = await deferToDatabase(factory.make_Zone)
        pod_info = self.make_pod_info()
        pod_info["zone"] = zone.id
        pod = await deferToDatabase(
            factory.make_Pod, pod_type=pod_info["type"]
        )
        pod_info["id"] = pod.id
        pod_info["name"] = factory.make_name("pod")
        await deferToDatabase(self.fake_pod_discovery)
        updated_pod = await handler.update(pod_info)
        self.assertEqual(pod_info["name"], updated_pod["name"])

    @wait_for_reactor
    async def test_update_succeeds_with_failed_refresh(self):
        def setup_fakes():
            self.fake_pod_discovery()
            failed_rack = factory.make_RackController()
            self.patch(vmhost, "discover_pod").return_value = (
                {},
                {failed_rack.system_id: factory.make_exception()},
            )

        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        zone = await deferToDatabase(factory.make_Zone)
        pod_info = self.make_pod_info()
        pod_info["zone"] = zone.id
        pod = await deferToDatabase(
            factory.make_Pod, pod_type=pod_info["type"]
        )
        pod_info["id"] = pod.id
        pod_info["name"] = factory.make_name("pod")
        await deferToDatabase(setup_fakes)
        updated_pod = await handler.update(pod_info)
        self.assertEqual(pod_info["name"], updated_pod["name"])

    @wait_for_reactor
    async def test_compose(self):
        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pod = await deferToDatabase(self.make_pod_with_hints)

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        node = await deferToDatabase(factory.make_Node)
        mock_compose_machine = self.patch(ComposeMachineForm, "compose")
        mock_compose_machine.return_value = succeed(node)

        observed_data = await handler.compose(
            {"id": pod.id, "skip_commissioning": True}
        )
        self.assertEqual(pod.id, observed_data["id"])

    @wait_for_reactor
    async def test_compose_hugepages(self):
        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pod = await deferToDatabase(self.make_pod_with_hints)

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        node = await deferToDatabase(factory.make_Node)

        orig_init = ComposeMachineForm.__init__

        def wrapped_init(obj, *args, **kwargs):
            self.form = obj
            return orig_init(obj, *args, **kwargs)

        self.patch(ComposeMachineForm, "__init__", wrapped_init)
        mock_compose_machine = self.patch(ComposeMachineForm, "compose")
        mock_compose_machine.return_value = succeed(node)
        await handler.compose(
            {
                "id": pod.id,
                "skip_commissioning": True,
                "hugepages_backed": True,
            }
        )
        self.assertTrue(self.form.get_value_for("hugepages_backed"))

    @wait_for_reactor
    async def test_compose_pinned_cores(self):
        user = await deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pod = await deferToDatabase(self.make_pod_with_hints)

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        node = await deferToDatabase(factory.make_Node)

        orig_init = ComposeMachineForm.__init__

        def wrapped_init(obj, *args, **kwargs):
            self.form = obj
            return orig_init(obj, *args, **kwargs)

        self.patch(ComposeMachineForm, "__init__", wrapped_init)
        mock_compose_machine = self.patch(ComposeMachineForm, "compose")
        mock_compose_machine.return_value = succeed(node)
        await handler.compose(
            {
                "id": pod.id,
                "skip_commissioning": True,
                "pinned_cores": [1, 2, 4],
            }
        )
        self.assertEqual(self.form.get_value_for("pinned_cores"), [1, 2, 4])
