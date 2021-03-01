# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the PodStoragePool model."""


from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPodStoragePool(MAASServerTestCase):
    def test_get_used_storage(self):
        pool = factory.make_PodStoragePool()
        size = 0
        for _ in range(3):
            disk = factory.make_VirtualMachineDisk(backing_pool=pool)
            size += disk.size
        self.assertEqual(size, pool.get_used_storage())

    def test_get_used_storage_returns_zero(self):
        pool = factory.make_PodStoragePool()
        self.assertEqual(0, pool.get_used_storage())
