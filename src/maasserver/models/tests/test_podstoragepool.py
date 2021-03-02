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
        for _ in range(3):
            vm = factory.make_VirtualMachine(project=project)
            disk = factory.make_VirtualMachineDisk(vm=vm, backing_pool=pool)
            size += disk.size
        # disks for VMs in other projects are not counted
        for _ in range(4):
            vm = factory.make_VirtualMachine(project=factory.make_string())
            factory.make_VirtualMachineDisk(vm=vm, backing_pool=pool)
        self.assertEqual(size, pool.get_used_storage())

    def test_get_used_storage_returns_zero(self):
        pool = factory.make_PodStoragePool()
        self.assertEqual(0, pool.get_used_storage())
