# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.pod`"""

__all__ = []

import random
from unittest.mock import MagicMock

from crochet import wait_for
from testtools.matchers import Equals
from twisted.internet.defer import inlineCallbacks, succeed

from maasserver.forms import pods
from maasserver.forms.pods import PodForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import reload_object
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.handlers.pod import ComposeMachineForm, PodHandler
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredMachine,
    DiscoveredPod,
    DiscoveredPodHints,
)

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
        self.patch(pods, "discover_pod").return_value = succeed(
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
                Capabilities.FIXED_LOCAL_STORAGE,
                Capabilities.ISCSI_STORAGE,
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

    def make_compose_machine_result(self, pod):
        composed_machine = DiscoveredMachine(
            hostname=factory.make_name("hostname"),
            architecture=pod.architectures[0],
            cores=1,
            memory=1024,
            cpu_speed=300,
            block_devices=[],
            interfaces=[],
        )
        pod_hints = DiscoveredPodHints(
            cores=random.randint(0, 10),
            memory=random.randint(1024, 4096),
            cpu_speed=random.randint(1000, 3000),
            local_storage=0,
        )
        return composed_machine, pod_hints

    def test_get(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        pod = self.make_pod_with_hints()
        # Create machines to test owners_count
        factory.make_Node()
        factory.make_Node(bmc=pod)
        factory.make_Node(bmc=pod, owner=admin)
        factory.make_Node(bmc=pod, owner=factory.make_User())
        expected_data = handler.full_dehydrate(pod)
        result = handler.get({"id": pod.id})
        self.assertItemsEqual(expected_data.keys(), result.keys())
        for key in expected_data:
            self.assertEqual(expected_data[key], result[key], key)
        self.assertThat(result, Equals(expected_data))
        self.assertThat(result["host"], Equals(None))
        self.assertThat(result["attached_vlans"], Equals([]))
        self.assertThat(result["boot_vlans"], Equals([]))
        self.assertThat(
            result["storage_pools"], Equals(expected_data["storage_pools"])
        )
        self.assertThat(result["owners_count"], Equals(2))
        self.assertEqual(result["numa_pinning"], [])

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
        pod = self.make_pod_with_hints(
            pod_type="lxd", host=node, ip_address=ip
        )
        factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[0],
            hugepages_backed=False,
            bmc=pod,
            machine=factory.make_Node(system_id="vm0"),
        )
        factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[2, 5],
            hugepages_backed=False,
            bmc=pod,
            machine=factory.make_Node(system_id="vm1"),
        )

        expected_data = handler.full_dehydrate(pod)
        result = handler.get({"id": pod.id})
        self.assertItemsEqual(expected_data.keys(), result.keys())
        for key in expected_data:
            self.assertEqual(expected_data[key], result[key], key)
        self.assertThat(result, Equals(expected_data))
        self.assertThat(result["host"], Equals(node.system_id))
        self.assertThat(result["attached_vlans"], Equals([subnet.vlan_id]))
        self.assertThat(result["boot_vlans"], Equals([subnet.vlan_id]))
        self.assertEqual(
            result["numa_pinning"],
            [
                {
                    "cores": {"allocated": [0], "free": [3]},
                    "interfaces": [
                        {
                            "id": 100,
                            "name": "eth4",
                            "virtual_functions": {"allocated": 4, "free": 12},
                        },
                        {
                            "id": 200,
                            "name": "eth5",
                            "virtual_functions": {"allocated": 14, "free": 2},
                        },
                    ],
                    "memory": {
                        "general": {"allocated": 1024, "free": 3072},
                        "hugepages": [],
                    },
                    "node_id": 0,
                    "vms": [
                        {
                            "pinned_cores": [0],
                            "system_id": "vm0",
                            "networks": [
                                {"guest_nic_id": 101, "host_nic_id": 100},
                                {"guest_nic_id": 102, "host_nic_id": 100},
                            ],
                        },
                    ],
                },
                {
                    "cores": {"allocated": [], "free": [1, 4]},
                    "interfaces": [
                        {
                            "id": 100,
                            "name": "eth4",
                            "virtual_functions": {"allocated": 4, "free": 12},
                        },
                        {
                            "id": 200,
                            "name": "eth5",
                            "virtual_functions": {"allocated": 14, "free": 2},
                        },
                    ],
                    "memory": {
                        "general": {"allocated": 0, "free": 1024},
                        "hugepages": [],
                    },
                    "node_id": 1,
                    "vms": [],
                },
                {
                    "cores": {"allocated": [2, 5], "free": []},
                    "interfaces": [
                        {
                            "id": 100,
                            "name": "eth4",
                            "virtual_functions": {"allocated": 4, "free": 12},
                        },
                        {
                            "id": 200,
                            "name": "eth5",
                            "virtual_functions": {"allocated": 14, "free": 2},
                        },
                    ],
                    "memory": {
                        "general": {"allocated": 1024, "free": 1024},
                        "hugepages": [],
                    },
                    "node_id": 2,
                    "vms": [
                        {
                            "pinned_cores": [2, 5],
                            "system_id": "vm1",
                            "networks": [
                                {"guest_nic_id": 101, "host_nic_id": 100},
                                {"guest_nic_id": 102, "host_nic_id": 100},
                            ],
                        },
                    ],
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
        self.assertItemsEqual(expected_data.keys(), result.keys())
        for key in expected_data:
            self.assertEqual(expected_data[key], result[key], key)
        self.assertThat(result, Equals(expected_data))
        self.assertThat(result["attached_vlans"], Equals([subnet.vlan_id]))
        self.assertThat(result["boot_vlans"], Equals([]))

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
        self.assertItemsEqual(
            ["edit", "delete", "compose"], result["permissions"]
        )

    def test_list(self):
        admin = factory.make_admin()
        handler = PodHandler(admin, {}, None)
        pod = self.make_pod_with_hints()
        expected_data = [handler.full_dehydrate(pod, for_list=True)]
        result = handler.list({"id": pod.id})
        self.assertThat(result, Equals(expected_data))

    @wait_for_reactor
    @inlineCallbacks
    def test_refresh(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pod = yield deferToDatabase(self.make_pod_with_hints)
        mock_discover_and_sync_pod = self.patch(
            PodForm, "discover_and_sync_pod"
        )
        mock_discover_and_sync_pod.return_value = succeed(pod)
        expected_data = yield deferToDatabase(
            handler.full_dehydrate, pod, for_list=False
        )
        observed_data = yield handler.refresh({"id": pod.id})
        self.assertThat(mock_discover_and_sync_pod, MockCalledOnceWith())
        self.assertItemsEqual(expected_data.keys(), observed_data.keys())
        for key in expected_data:
            self.assertEqual(expected_data[key], observed_data[key], key)
        self.assertEqual(expected_data, observed_data)

    @wait_for_reactor
    @inlineCallbacks
    def test_delete(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pod = yield deferToDatabase(self.make_pod_with_hints)
        yield handler.delete({"id": pod.id})
        expected_pod = yield deferToDatabase(reload_object, pod)
        self.assertIsNone(expected_pod)

    @wait_for_reactor
    @inlineCallbacks
    def test_create(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        zone = yield deferToDatabase(factory.make_Zone)
        pod_info = self.make_pod_info()
        pod_info["zone"] = zone.id
        yield deferToDatabase(self.fake_pod_discovery)
        created_pod = yield handler.create(pod_info)
        self.assertIsNotNone(created_pod["id"])

    @wait_for_reactor
    @inlineCallbacks
    def test_create_with_pool(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pool = yield deferToDatabase(factory.make_ResourcePool)
        pod_info = self.make_pod_info()
        pod_info["pool"] = pool.id
        yield deferToDatabase(self.fake_pod_discovery)
        created_pod = yield handler.create(pod_info)
        self.assertEqual(pool.id, created_pod["pool"])

    @wait_for_reactor
    @inlineCallbacks
    def test_update(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        zone = yield deferToDatabase(factory.make_Zone)
        pod_info = self.make_pod_info()
        pod_info["zone"] = zone.id
        pod = yield deferToDatabase(
            factory.make_Pod, pod_type=pod_info["type"]
        )
        pod_info["id"] = pod.id
        pod_info["name"] = factory.make_name("pod")
        yield deferToDatabase(self.fake_pod_discovery)
        updated_pod = yield handler.update(pod_info)
        self.assertEqual(pod_info["name"], updated_pod["name"])

    @wait_for_reactor
    @inlineCallbacks
    def test_compose(self):
        user = yield deferToDatabase(factory.make_admin)
        handler = PodHandler(user, {}, None)
        pod = yield deferToDatabase(self.make_pod_with_hints)

        # Mock the RPC client.
        client = MagicMock()
        mock_getClient = self.patch(pods, "getClientFromIdentifiers")
        mock_getClient.return_value = succeed(client)

        # Mock the result of the composed machine.
        node = yield deferToDatabase(factory.make_Node)
        mock_compose_machine = self.patch(ComposeMachineForm, "compose")
        mock_compose_machine.return_value = succeed(node)

        observed_data = yield handler.compose(
            {"id": pod.id, "skip_commissioning": True}
        )
        self.assertEqual(pod.id, observed_data["id"])
