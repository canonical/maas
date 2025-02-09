# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the PodStoragePool model."""

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPodStoragePool(MAASServerTestCase):
    def test_get_used_storage(self):
        project = factory.make_string()
        pod = factory.make_Pod(parameters={"project": project})
        pool = factory.make_PodStoragePool(pod=pod)
        size = 0
        for _ in range(2):
            vm = factory.make_VirtualMachine(project=project)
            disk = factory.make_VirtualMachineDisk(vm=vm, backing_pool=pool)
            size += disk.size
        # disks for VMs in other projects are not counted
        vm = factory.make_VirtualMachine(project=factory.make_string())
        factory.make_VirtualMachineDisk(vm=vm, backing_pool=pool)
        self.assertEqual(size, pool.get_used_storage())

    def test_get_used_storage_only_current_disks(self):
        project = factory.make_string()
        pod = factory.make_Pod(parameters={"project": project})
        pool = factory.make_PodStoragePool(pod=pod)

        node = factory.make_Node(with_boot_disk=False)
        other_node_config = factory.make_NodeConfig(
            node=node, name="deployment"
        )
        disk = factory.make_PhysicalBlockDevice(node=node)
        disk_other_config = factory.make_PhysicalBlockDevice(
            node_config=other_node_config
        )

        vm = factory.make_VirtualMachine(project=project, machine=node)
        vmdisk1 = factory.make_VirtualMachineDisk(
            vm=vm, backing_pool=pool, block_device=disk
        )
        vmdisk2 = factory.make_VirtualMachineDisk(vm=vm, backing_pool=pool)
        # a disk in a different node config does not contribute to count
        factory.make_VirtualMachineDisk(
            vm=vm, backing_pool=pool, block_device=disk_other_config
        )
        self.assertEqual(pool.get_used_storage(), vmdisk1.size + vmdisk2.size)

    def test_get_used_storage_returns_zero(self):
        pool = factory.make_PodStoragePool()
        self.assertEqual(0, pool.get_used_storage())
