# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import asdict
import random

from django.core.exceptions import ValidationError

from maasserver.enum import INTERFACE_TYPE
from maasserver.models.virtualmachine import (
    get_vm_host_resources,
    get_vm_host_used_resources,
    MB,
    VirtualMachine,
    VirtualMachineInterface,
    VMHostNetworkInterface,
    VMHostResource,
    VMHostVirtualMachineResources,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.drivers.pod import InterfaceAttachType


class TestVirtualMachine(MAASServerTestCase):
    def test_instantiate_defaults(self):
        bmc = factory.make_BMC(power_type="lxd")
        vm = VirtualMachine(identifier="vm1", bmc=bmc, project="prj1")
        vm.save()
        self.assertEqual(vm.identifier, "vm1")
        self.assertIs(vm.bmc, bmc)
        self.assertEqual(vm.project, "prj1")
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
            project="prj1",
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
            project="prj1",
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
        resources = get_vm_host_resources(pod)
        self.assertEqual(resources.cores.free, 0)
        self.assertEqual(resources.cores.allocated, 0)
        self.assertEqual(resources.memory.general.free, 0)
        self.assertEqual(resources.memory.general.allocated, 0)
        self.assertEqual(resources.memory.hugepages.free, 0)
        self.assertEqual(resources.memory.hugepages.allocated, 0)
        self.assertEqual(resources.numa, [])
        self.assertEqual(resources.vms, [])

    def test_get_resources_no_detailed(self):
        pod = factory.make_Pod(pod_type="lxd", host=factory.make_Node())
        factory.make_VirtualMachine(bmc=pod)
        resources = get_vm_host_resources(pod, detailed=False)
        # NUMA info and VMs list are not included when not in detailed mode
        self.assertEqual(resources.numa, [])
        self.assertEqual(resources.vms, [])

    def test_get_resources_global_resources(self):
        node = factory.make_Node()
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 1]
        numa_node0.memory = 4096
        numa_node0.save()
        factory.make_NUMANode(node=node, cores=[2, 3], memory=2048)
        factory.make_NUMANode(node=node, cores=[4, 5], memory=2048)
        factory.make_NUMANode(node=node, cores=[6, 7], memory=2048)
        factory.make_NUMANodeHugepages(
            numa_node=numa_node0, page_size=1024 * MB, total=2048 * MB
        )
        project = factory.make_string()
        pod = factory.make_Pod(
            pod_type="lxd", parameters={"project": project}, host=node
        )
        pool1 = factory.make_PodStoragePool(pod=pod)
        pool2 = factory.make_PodStoragePool(pod=pod)
        vm1 = factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[0, 1],
            hugepages_backed=False,
            bmc=pod,
            project=project,
        )
        disk1 = factory.make_VirtualMachineDisk(vm=vm1, backing_pool=pool1)
        vm2 = factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[2],
            hugepages_backed=False,
            bmc=pod,
        )
        disk2 = factory.make_VirtualMachineDisk(vm=vm2, backing_pool=pool2)
        factory.make_VirtualMachine(
            memory=1024,
            unpinned_cores=2,
            hugepages_backed=True,
            project=project,
            bmc=pod,
        )
        factory.make_VirtualMachine(
            memory=2048, unpinned_cores=1, hugepages_backed=False, bmc=pod
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(resources.vm_count.tracked, 2)
        self.assertEqual(resources.vm_count.other, 2)
        self.assertEqual(resources.cores.free, 2)
        self.assertEqual(resources.cores.allocated, 6)
        self.assertEqual(resources.cores.allocated_tracked, 4)
        self.assertEqual(resources.cores.allocated_other, 2)
        self.assertEqual(resources.memory.general.free, 6144 * MB)
        self.assertEqual(resources.memory.general.allocated, 4096 * MB)
        self.assertEqual(resources.memory.general.allocated_tracked, 1024 * MB)
        self.assertEqual(resources.memory.general.allocated_other, 3072 * MB)
        self.assertEqual(resources.memory.hugepages.free, 1024 * MB)
        self.assertEqual(resources.memory.hugepages.allocated, 1024 * MB)
        self.assertEqual(
            resources.memory.hugepages.allocated_tracked, 1024 * MB
        )
        self.assertEqual(resources.memory.hugepages.allocated_other, 0)
        self.assertEqual(resources.storage.allocated_tracked, disk1.size)
        self.assertEqual(resources.storage.allocated_other, disk2.size)
        self.assertEqual(
            resources.storage.free,
            pool1.storage + pool2.storage - disk1.size - disk2.size,
        )

    def test_get_resources_vms(self):
        node = factory.make_Node()
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 1, 2, 3]
        numa_node0.memory = 4096
        numa_node0.save()
        project = factory.make_string()
        pod = factory.make_Pod(
            pod_type="lxd", parameters={"project": project}, host=node
        )
        node = factory.make_Node(bmc=pod)
        vm0 = factory.make_VirtualMachine(
            machine=node,
            memory=1024,
            pinned_cores=[0, 1],
            hugepages_backed=False,
            bmc=pod,
            project=project,
        )
        vm1 = factory.make_VirtualMachine(
            memory=1024,
            unpinned_cores=2,
            hugepages_backed=True,
            bmc=pod,
            project=project,
        )
        # another VM, in a different project
        factory.make_VirtualMachine(
            memory=1024,
            unpinned_cores=2,
            bmc=pod,
            project=factory.make_string(),
        )
        resources = get_vm_host_resources(pod)
        self.assertCountEqual(
            resources.vms,
            [
                VMHostVirtualMachineResources(
                    id=vm0.id,
                    system_id=node.system_id,
                    pinned_cores=[0, 1],
                    unpinned_cores=0,
                    memory=1024 * MB,
                    hugepages_backed=False,
                ),
                VMHostVirtualMachineResources(
                    id=vm1.id,
                    system_id=None,
                    pinned_cores=[],
                    unpinned_cores=2,
                    memory=1024 * MB,
                    hugepages_backed=True,
                ),
            ],
        )

    def test_get_resources_global_resources_pinned_cores_overlap(self):
        node = factory.make_Node()
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 1]
        numa_node0.memory = 4096
        numa_node0.save()
        factory.make_NUMANode(node=node, cores=[2, 3], memory=2048)
        pod = factory.make_Pod(pod_type="lxd", host=node)
        factory.make_VirtualMachine(
            pinned_cores=[0, 1],
            bmc=pod,
        )
        factory.make_VirtualMachine(
            pinned_cores=[1, 2],
            bmc=pod,
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(resources.cores.free, 0)
        self.assertEqual(resources.cores.allocated, 4)

    def test_get_resources_interfaces(self):
        node = factory.make_Node()
        if0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth0",
            numa_node=node.default_numanode,
            sriov_max_vf=8,
        )
        if1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth1",
            numa_node=factory.make_NUMANode(node=node),
            sriov_max_vf=4,
        )
        project = factory.make_string()
        pod = factory.make_Pod(
            pod_type="lxd",
            parameters={"project": project},
            host=node,
        )
        vm0 = factory.make_VirtualMachine(bmc=pod, project=project)
        for _ in range(3):
            VirtualMachineInterface.objects.create(
                vm=vm0,
                host_interface=if0,
                attachment_type=InterfaceAttachType.SRIOV,
            )
        vm1 = factory.make_VirtualMachine(
            bmc=pod, project=factory.make_string()
        )
        for _ in range(2):
            VirtualMachineInterface.objects.create(
                vm=vm1,
                host_interface=if0,
                attachment_type=InterfaceAttachType.SRIOV,
            )
        vm2 = factory.make_VirtualMachine(bmc=pod)
        for _ in range(2):
            VirtualMachineInterface.objects.create(
                vm=vm2,
                host_interface=if1,
                attachment_type=InterfaceAttachType.SRIOV,
            )
        resources = get_vm_host_resources(pod)
        self.assertCountEqual(
            resources.interfaces,
            [
                VMHostNetworkInterface(
                    id=if0.id,
                    name="eth0",
                    numa_index=0,
                    virtual_functions=VMHostResource(
                        allocated_tracked=3,
                        allocated_other=2,
                        free=3,
                    ),
                ),
                VMHostNetworkInterface(
                    id=if1.id,
                    name="eth1",
                    numa_index=1,
                    virtual_functions=VMHostResource(
                        allocated_tracked=0,
                        allocated_other=2,
                        free=2,
                    ),
                ),
            ],
        )

    def test_get_resources_interfaces_no_vm_link(self):
        node = factory.make_Node()
        iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth0",
            numa_node=node.default_numanode,
            sriov_max_vf=8,
        )
        pod = factory.make_Pod(
            pod_type="lxd",
            host=node,
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            resources.interfaces,
            [
                VMHostNetworkInterface(
                    id=iface.id,
                    name="eth0",
                    numa_index=0,
                    virtual_functions=VMHostResource(
                        allocated_tracked=0,
                        allocated_other=0,
                        free=8,
                    ),
                ),
            ],
        )

    def test_get_resources_interfaces_not_sriov(self):
        node = factory.make_Node()
        iface = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth0",
            numa_node=node.default_numanode,
            sriov_max_vf=8,
        )
        project = factory.make_string()
        pod = factory.make_Pod(
            pod_type="lxd",
            parameters={"project": project},
            host=node,
        )
        VirtualMachineInterface.objects.create(
            vm=factory.make_VirtualMachine(bmc=pod, project=project),
            host_interface=iface,
            attachment_type=InterfaceAttachType.BRIDGE,
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            resources.interfaces,
            [
                VMHostNetworkInterface(
                    id=iface.id,
                    name="eth0",
                    numa_index=0,
                    virtual_functions=VMHostResource(
                        allocated_tracked=0,
                        allocated_other=0,
                        free=8,
                    ),
                ),
            ],
        )

    def test_get_resources_numa_aligned(self):
        node = factory.make_Node()
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 3]
        numa_node0.memory = 4096
        numa_node0.save()
        factory.make_NUMANode(node=node, cores=[1, 4], memory=1024)
        factory.make_NUMANode(node=node, cores=[2, 5], memory=2048)
        pod = factory.make_Pod(pod_type="lxd", host=node)
        vm0 = factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[0],
            hugepages_backed=False,
            bmc=pod,
        )
        vm1 = factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[2, 5],
            hugepages_backed=False,
            bmc=pod,
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            [asdict(r) for r in resources.numa],
            [
                {
                    "cores": {"allocated": [0], "free": [3]},
                    "memory": {
                        "general": {"allocated": 1024 * MB, "free": 3072 * MB},
                        "hugepages": [],
                    },
                    "interfaces": [],
                    "node_id": 0,
                    "vms": [vm0.id],
                },
                {
                    "cores": {"allocated": [], "free": [1, 4]},
                    "memory": {
                        "general": {"allocated": 0, "free": 1024 * MB},
                        "hugepages": [],
                    },
                    "interfaces": [],
                    "node_id": 1,
                    "vms": [],
                },
                {
                    "cores": {"allocated": [2, 5], "free": []},
                    "memory": {
                        "general": {"allocated": 1024 * MB, "free": 1024 * MB},
                        "hugepages": [],
                    },
                    "interfaces": [],
                    "node_id": 2,
                    "vms": [vm1.id],
                },
            ],
        )

    def test_get_resources_numa_aligned_hugepages(self):
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
        vm0 = factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[0],
            hugepages_backed=True,
            bmc=pod,
        )
        vm1 = factory.make_VirtualMachine(
            memory=1024,
            pinned_cores=[2, 3],
            hugepages_backed=True,
            bmc=pod,
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            [asdict(r) for r in resources.numa],
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
                    "interfaces": [],
                    "node_id": 0,
                    "vms": [vm0.id],
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
                    "interfaces": [],
                    "node_id": 1,
                    "vms": [vm1.id],
                },
            ],
        )

    def test_get_resources_numa_unaligned(self):
        node = factory.make_Node()
        numa_node0 = node.default_numanode
        numa_node0.cores = [0, 1]
        numa_node0.memory = 4096
        numa_node0.save()
        factory.make_NUMANode(node=node, cores=[2, 3], memory=2048)
        pod = factory.make_Pod(pod_type="lxd")
        pod.hints.nodes.add(node)
        vm = factory.make_VirtualMachine(
            memory=2048,
            pinned_cores=[0, 2],
            hugepages_backed=False,
            bmc=pod,
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            [asdict(r) for r in resources.numa],
            [
                {
                    "cores": {"allocated": [0], "free": [1]},
                    "memory": {
                        "general": {"allocated": 1024 * MB, "free": 3072 * MB},
                        "hugepages": [],
                    },
                    "interfaces": [],
                    "node_id": 0,
                    "vms": [vm.id],
                },
                {
                    "cores": {"allocated": [2], "free": [3]},
                    "memory": {
                        "general": {"allocated": 1024 * MB, "free": 1024 * MB},
                        "hugepages": [],
                    },
                    "interfaces": [],
                    "node_id": 1,
                    "vms": [vm.id],
                },
            ],
        )

    def test_get_resources_numa_unaligned_hugepages(self):
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
        vm = factory.make_VirtualMachine(
            memory=2048,
            pinned_cores=[0, 2],
            hugepages_backed=True,
            bmc=pod,
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            [asdict(r) for r in resources.numa],
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
                    "interfaces": [],
                    "node_id": 0,
                    "vms": [vm.id],
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
                    "interfaces": [],
                    "node_id": 1,
                    "vms": [vm.id],
                },
            ],
        )

    def test_get_resources_numa_hugepages_round(self):
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
        vm = factory.make_VirtualMachine(
            memory=2048,
            pinned_cores=[0, 2],
            hugepages_backed=True,
            bmc=pod,
        )
        resources = get_vm_host_resources(pod)
        self.assertEqual(
            [asdict(r) for r in resources.numa],
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
                    "interfaces": [],
                    "node_id": 0,
                    "vms": [vm.id],
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
                    "interfaces": [],
                    "node_id": 1,
                    "vms": [vm.id],
                },
            ],
        )


class TestGetVMHostUsedResources(MAASServerTestCase):
    def test_get_used_resources(self):
        project = factory.make_string()
        vmhost = factory.make_Pod(
            pod_type="lxd",
            parameters={"project": project},
        )
        pool1 = factory.make_PodStoragePool(pod=vmhost)
        pool2 = factory.make_PodStoragePool(pod=vmhost)

        vm1 = factory.make_VirtualMachine(
            bmc=vmhost,
            project=project,
            memory=1024,
            pinned_cores=[0, 1, 2],
            hugepages_backed=False,
        )
        factory.make_VirtualMachineDisk(vm=vm1, backing_pool=pool1, size=1000)
        vm2 = factory.make_VirtualMachine(
            bmc=vmhost,
            project=project,
            memory=2048,
            unpinned_cores=2,
            hugepages_backed=False,
        )
        factory.make_VirtualMachineDisk(vm=vm2, backing_pool=pool2, size=2000)
        vm3 = factory.make_VirtualMachine(
            bmc=vmhost,
            project=project,
            memory=4096,
            unpinned_cores=4,
            hugepages_backed=True,
        )
        factory.make_VirtualMachineDisk(vm=vm3, backing_pool=pool1, size=500)

        used_resources = get_vm_host_used_resources(vmhost)
        self.assertEqual(used_resources.cores, 9)
        self.assertEqual(used_resources.memory, 3072)
        self.assertEqual(used_resources.hugepages_memory, 4096)
        self.assertEqual(used_resources.total_memory, 7168)
        self.assertEqual(used_resources.storage, 3500)

    def test_get_used_resources_only_tracked_project(self):
        project = factory.make_string()
        vmhost = factory.make_Pod(
            pod_type="lxd",
            parameters={"project": project},
        )
        pool = factory.make_PodStoragePool(pod=vmhost)

        vm = factory.make_VirtualMachine(
            bmc=vmhost,
            project=factory.make_string(),
            memory=1024,
            pinned_cores=[0, 1, 2],
            hugepages_backed=False,
        )
        factory.make_VirtualMachineDisk(vm=vm, backing_pool=pool, size=1000)
        used_resources = get_vm_host_used_resources(vmhost)
        self.assertEqual(used_resources.cores, 0)
        self.assertEqual(used_resources.memory, 0)
        self.assertEqual(used_resources.hugepages_memory, 0)
        self.assertEqual(used_resources.storage, 0)
