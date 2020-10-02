# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import asdict
import random

from django.core.exceptions import ValidationError

from maasserver.models.virtualmachine import (
    get_vm_host_resources,
    MB,
    VirtualMachine,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestVirtualMachine(MAASServerTestCase):
    def test_instantiate_defaults(self):
        bmc = factory.make_BMC(power_type="lxd")
        vm = VirtualMachine(identifier="vm1", bmc=bmc)
        vm.save()
        self.assertEqual(vm.identifier, "vm1")
        self.assertIs(vm.bmc, bmc)
        self.assertEqual(vm.unpinned_cores, 0)
        self.assertEqual(vm.pinned_cores, [])
        self.assertEqual(vm.memory, 0)
        self.assertFalse(vm.hugepages_backed)
        self.assertIsNone(vm.machine)

    def test_instantiate_extra_fields(self):
        memory = 1024 * random.randint(1, 256)
        machine = factory.make_Machine()
        hugepages_backed = factory.pick_bool()
        vm = VirtualMachine(
            identifier="vm1",
            bmc=factory.make_BMC(power_type="lxd"),
            memory=memory,
            machine=machine,
            hugepages_backed=hugepages_backed,
        )
        vm.save()
        self.assertEqual(vm.unpinned_cores, 0)
        self.assertEqual(vm.pinned_cores, [])
        self.assertEqual(vm.memory, memory)
        self.assertEqual(vm.hugepages_backed, hugepages_backed)
        self.assertIs(vm.machine, machine)

    def test_instantiate_pinned_cores(self):
        vm = factory.make_VirtualMachine(pinned_cores=[1, 2, 3])
        self.assertEqual(vm.pinned_cores, [1, 2, 3])

    def test_instantiate_unpinned_cores(self):
        vm = factory.make_VirtualMachine(unpinned_cores=4)
        self.assertEqual(vm.unpinned_cores, 4)

    def test_instantiate_validate_cores(self):
        self.assertRaises(
            ValidationError,
            factory.make_VirtualMachine,
            pinned_cores=[1, 2, 3],
            unpinned_cores=4,
        )

    def test_machine_virtualmachine(self):
        machine = factory.make_Machine()
        vm = VirtualMachine.objects.create(
            identifier="vm1",
            bmc=factory.make_BMC(power_type="lxd"),
            machine=machine,
        )
        self.assertIs(machine.virtualmachine, vm)


class TestGetVMHostResources(MAASServerTestCase):
    def test_get_resources_no_host(self):
        pod = factory.make_Pod(pod_type="lxd", host=None)
        factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[0, 2],
            bmc=pod,
        )
        self.assertEqual(get_vm_host_resources(pod), [])

    def test_get_resources_aligned(self):
        node = factory.make_Node()
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 3]
        numa_node0.memory = 4096
        numa_node0.save()
        factory.make_NUMANode(node=node, cores=[1, 4], memory=1024)
        factory.make_NUMANode(node=node, cores=[2, 5], memory=2048)
        pod = factory.make_Pod(pod_type="lxd", host=node)
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
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            [asdict(r) for r in resources],
            [
                {
                    "cores": {"allocated": [0], "free": [3]},
                    "memory": {
                        "general": {"allocated": 1024 * MB, "free": 3072 * MB},
                        "hugepages": [],
                    },
                    "node_id": 0,
                    "vms": [{"pinned_cores": [0], "system_id": "vm0"}],
                },
                {
                    "cores": {"allocated": [], "free": [1, 4]},
                    "memory": {
                        "general": {"allocated": 0, "free": 1024 * MB},
                        "hugepages": [],
                    },
                    "node_id": 1,
                    "vms": [],
                },
                {
                    "cores": {"allocated": [2, 5], "free": []},
                    "memory": {
                        "general": {"allocated": 1024 * MB, "free": 1024 * MB},
                        "hugepages": [],
                    },
                    "node_id": 2,
                    "vms": [{"pinned_cores": [2, 5], "system_id": "vm1"}],
                },
            ],
        )

    def test_get_resources_aligned_hugepages(self):
        node = factory.make_Node()
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 1]
        numa_node0.memory = 4096
        numa_node0.save()
        numa_node1 = factory.make_NUMANode(
            node=node, cores=[2, 3], memory=8192
        )
        factory.make_NUMANodeHugepages(
            numa_node=numa_node0, page_size=1024 * MB, total=1024 * MB
        )
        factory.make_NUMANodeHugepages(
            numa_node=numa_node1, page_size=1024 * MB, total=4096 * MB
        )
        pod = factory.make_Pod(pod_type="lxd")
        pod.hints.nodes.add(node)
        factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[0],
            hugepages_backed=True,
            bmc=pod,
            machine=factory.make_Node(system_id="vm0"),
        )
        factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[2, 3],
            hugepages_backed=True,
            bmc=pod,
            machine=factory.make_Node(system_id="vm1"),
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            [asdict(r) for r in resources],
            [
                {
                    "cores": {"allocated": [0], "free": [1]},
                    "memory": {
                        "general": {"allocated": 0, "free": 3072 * MB},
                        "hugepages": [
                            {
                                "allocated": 1024 * MB,
                                "free": 0,
                                "page_size": 1024 * MB,
                            }
                        ],
                    },
                    "node_id": 0,
                    "vms": [{"pinned_cores": [0], "system_id": "vm0"}],
                },
                {
                    "cores": {"allocated": [2, 3], "free": []},
                    "memory": {
                        "general": {"allocated": 0, "free": 4096 * MB},
                        "hugepages": [
                            {
                                "allocated": 1024 * MB,
                                "free": 3072 * MB,
                                "page_size": 1024 * MB,
                            }
                        ],
                    },
                    "node_id": 1,
                    "vms": [{"pinned_cores": [2, 3], "system_id": "vm1"}],
                },
            ],
        )

    def test_get_resources_unaligned(self):
        node = factory.make_Node()
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 1]
        numa_node0.memory = 4096
        numa_node0.save()
        factory.make_NUMANode(node=node, cores=[2, 3], memory=2048)
        pod = factory.make_Pod(pod_type="lxd")
        pod.hints.nodes.add(node)
        factory.make_VirtualMachine(
            memory=2048,
            pinned_cores=[0, 2],
            hugepages_backed=False,
            bmc=pod,
            machine=factory.make_Node(system_id="vm0"),
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            [asdict(r) for r in resources],
            [
                {
                    "cores": {"allocated": [0], "free": [1]},
                    "memory": {
                        "general": {"allocated": 1024 * MB, "free": 3072 * MB},
                        "hugepages": [],
                    },
                    "node_id": 0,
                    "vms": [{"pinned_cores": [0], "system_id": "vm0"}],
                },
                {
                    "cores": {"allocated": [2], "free": [3]},
                    "memory": {
                        "general": {"allocated": 1024 * MB, "free": 1024 * MB},
                        "hugepages": [],
                    },
                    "node_id": 1,
                    "vms": [{"pinned_cores": [2], "system_id": "vm0"}],
                },
            ],
        )

    def test_get_resources_unaligned_hugepages(self):
        node = factory.make_Node()
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 1]
        numa_node0.memory = 4096
        numa_node0.save()
        numa_node1 = factory.make_NUMANode(
            node=node, cores=[2, 3], memory=4096
        )
        factory.make_NUMANodeHugepages(
            numa_node=numa_node0, page_size=1024 * MB, total=1024 * MB
        )
        factory.make_NUMANodeHugepages(
            numa_node=numa_node1, page_size=1024 * MB, total=4096 * MB
        )
        pod = factory.make_Pod(pod_type="lxd")
        pod.hints.nodes.add(node)
        factory.make_VirtualMachine(
            memory=2048,
            pinned_cores=[0, 2],
            hugepages_backed=True,
            bmc=pod,
            machine=factory.make_Node(system_id="vm0"),
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            [asdict(r) for r in resources],
            [
                {
                    "cores": {"allocated": [0], "free": [1]},
                    "memory": {
                        "general": {"allocated": 0, "free": 3072 * MB},
                        "hugepages": [
                            {
                                "allocated": 1024 * MB,
                                "free": 0,
                                "page_size": 1024 * MB,
                            }
                        ],
                    },
                    "node_id": 0,
                    "vms": [{"pinned_cores": [0], "system_id": "vm0"}],
                },
                {
                    "cores": {"allocated": [2], "free": [3]},
                    "memory": {
                        "general": {"allocated": 0, "free": 0},
                        "hugepages": [
                            {
                                "allocated": 1024 * MB,
                                "free": 3072 * MB,
                                "page_size": 1024 * MB,
                            }
                        ],
                    },
                    "node_id": 1,
                    "vms": [{"pinned_cores": [2], "system_id": "vm0"}],
                },
            ],
        )

    def test_get_resources_hugepages_round(self):
        node = factory.make_Node()
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 1]
        numa_node0.memory = 4096
        numa_node0.save()
        numa_node1 = factory.make_NUMANode(
            node=node, cores=[2, 3], memory=8192
        )
        factory.make_NUMANodeHugepages(
            numa_node=numa_node0, page_size=2048 * MB, total=4096 * MB
        )
        factory.make_NUMANodeHugepages(
            numa_node=numa_node1, page_size=4096 * MB, total=8192 * MB
        )
        pod = factory.make_Pod(pod_type="lxd")
        pod.hints.nodes.add(node)
        factory.make_VirtualMachine(
            memory=2048,
            pinned_cores=[0, 2],
            hugepages_backed=True,
            bmc=pod,
            machine=factory.make_Node(system_id="vm0"),
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            [asdict(r) for r in resources],
            [
                {
                    "cores": {"allocated": [0], "free": [1]},
                    "memory": {
                        "general": {"allocated": 0, "free": 0},
                        "hugepages": [
                            {
                                "allocated": 2048 * MB,
                                "free": 2048 * MB,
                                "page_size": 2048 * MB,
                            }
                        ],
                    },
                    "node_id": 0,
                    "vms": [{"pinned_cores": [0], "system_id": "vm0"}],
                },
                {
                    "cores": {"allocated": [2], "free": [3]},
                    "memory": {
                        "general": {"allocated": 0, "free": 0},
                        "hugepages": [
                            {
                                "allocated": 4096 * MB,
                                "free": 4096 * MB,
                                "page_size": 4096 * MB,
                            }
                        ],
                    },
                    "node_id": 1,
                    "vms": [{"pinned_cores": [2], "system_id": "vm0"}],
                },
            ],
        )
