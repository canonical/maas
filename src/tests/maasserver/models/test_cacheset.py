# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `CacheSet`."""

import random

from django.core.exceptions import PermissionDenied
from django.http import Http404

from maasserver.enum import FILESYSTEM_GROUP_TYPE, FILESYSTEM_TYPE
from maasserver.models import CacheSet
from maasserver.permissions import NodePermission
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestCacheSetManager(MAASServerTestCase):
    """Tests for the `CacheSet` model manager."""

    def test_get_cache_set_idx(self):
        node = factory.make_Node()
        cache_set_zero = factory.make_CacheSet(node=node)
        cache_set_one = factory.make_CacheSet(node=node)
        self.assertEqual(0, CacheSet.objects.get_cache_set_idx(cache_set_zero))
        self.assertEqual(1, CacheSet.objects.get_cache_set_idx(cache_set_one))

    def test_get_cache_sets_for_node(self):
        node = factory.make_Node()
        cache_sets = [factory.make_CacheSet(node=node) for _ in range(3)]
        self.assertCountEqual(
            cache_sets, CacheSet.objects.get_cache_sets_for_node(node)
        )

    def test_get_cache_set_for_block_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        cache_set = factory.make_CacheSet(block_device=block_device)
        self.assertEqual(
            cache_set,
            CacheSet.objects.get_cache_set_for_block_device(block_device),
        )

    def test_get_cache_set_for_partition(self):
        partition = factory.make_Partition()
        cache_set = factory.make_CacheSet(partition=partition)
        self.assertEqual(
            cache_set, CacheSet.objects.get_cache_set_for_partition(partition)
        )

    def test_get_or_create_cache_set_for_block_device_creates_new(self):
        block_device = factory.make_PhysicalBlockDevice()
        cache_set = CacheSet.objects.get_or_create_cache_set_for_block_device(
            block_device
        )
        self.assertEqual(block_device, cache_set.get_device())

    def test_get_or_create_cache_set_for_block_device_returns_previous(self):
        block_device = factory.make_PhysicalBlockDevice()
        cache_set = CacheSet.objects.get_or_create_cache_set_for_block_device(
            block_device
        )
        cache_set_prev = (
            CacheSet.objects.get_or_create_cache_set_for_block_device(
                block_device
            )
        )
        self.assertEqual(cache_set_prev, cache_set)

    def test_get_or_create_cache_set_for_partition_creates_new(self):
        partition = factory.make_Partition()
        cache_set = CacheSet.objects.get_or_create_cache_set_for_partition(
            partition
        )
        self.assertEqual(partition, cache_set.get_device())

    def test_get_or_create_cache_set_for_partition_returns_previous(self):
        partition = factory.make_Partition()
        cache_set = CacheSet.objects.get_or_create_cache_set_for_partition(
            partition
        )
        cache_set_prev = (
            CacheSet.objects.get_or_create_cache_set_for_partition(partition)
        )
        self.assertEqual(cache_set_prev, cache_set)

    def test_get_cache_set_by_id_or_name_by_id(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        self.assertEqual(
            cache_set,
            CacheSet.objects.get_cache_set_by_id_or_name(cache_set.id, node),
        )

    def test_get_cache_set_by_id_or_name_by_id_invalid_for_mismatch_node(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        self.assertRaises(
            CacheSet.DoesNotExist,
            CacheSet.objects.get_cache_set_by_id_or_name,
            cache_set.id,
            factory.make_Node(),
        )

    def test_get_cache_set_by_id_or_name_by_name(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        self.assertEqual(
            cache_set,
            CacheSet.objects.get_cache_set_by_id_or_name(cache_set.name, node),
        )

    def test_get_cache_set_by_id_or_name_raises_error_for_invalid_name(self):
        self.assertRaises(
            CacheSet.DoesNotExist,
            CacheSet.objects.get_cache_set_by_id_or_name,
            "cakhe",
            factory.make_Node(),
        )

    def test_get_cache_set_by_id_or_name_raises_error_for_invalid_idx(self):
        self.assertRaises(
            CacheSet.DoesNotExist,
            CacheSet.objects.get_cache_set_by_id_or_name,
            "cacheX",
            factory.make_Node(),
        )

    def test_get_cache_set_by_id_or_name_raises_error_for_missing_idx(self):
        self.assertRaises(
            CacheSet.DoesNotExist,
            CacheSet.objects.get_cache_set_by_id_or_name,
            "cache",
            factory.make_Node(),
        )

    def test_get_cache_set_by_id_or_name_raises_error_for_not_exist_idx(self):
        self.assertRaises(
            CacheSet.DoesNotExist,
            CacheSet.objects.get_cache_set_by_id_or_name,
            "cache20",
            factory.make_Node(),
        )


class TestCacheSetManagerGetCacheSetOr404(MAASServerTestCase):
    """Tests for the `CacheSetManager.get_cache_set_or_404`."""

    def test_raises_Http404_when_invalid_node(self):
        user = factory.make_admin()
        cache_set = factory.make_CacheSet()
        self.assertRaises(
            Http404,
            CacheSet.objects.get_cache_set_or_404,
            factory.make_name("system_id"),
            cache_set.id,
            user,
            NodePermission.view,
        )

    def test_raises_Http404_when_invalid_device(self):
        user = factory.make_admin()
        node = factory.make_Node()
        self.assertRaises(
            Http404,
            CacheSet.objects.get_cache_set_or_404,
            node.system_id,
            random.randint(0, 100),
            user,
            NodePermission.view,
        )

    def test_return_cache_set_by_name(self):
        user = factory.make_User()
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        self.assertEqual(
            cache_set.id,
            CacheSet.objects.get_cache_set_or_404(
                node.system_id, cache_set.name, user, NodePermission.view
            ).id,
        )

    def test_view_returns_cache_set_when_no_owner(self):
        user = factory.make_User()
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        self.assertEqual(
            cache_set.id,
            CacheSet.objects.get_cache_set_or_404(
                node.system_id, cache_set.id, user, NodePermission.view
            ).id,
        )

    def test_view_returns_cache_set_when_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        cache_set = factory.make_CacheSet(node=node)
        self.assertEqual(
            cache_set.id,
            CacheSet.objects.get_cache_set_or_404(
                node.system_id, cache_set.id, user, NodePermission.view
            ).id,
        )

    def test_edit_raises_PermissionDenied_when_user_not_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=factory.make_User())
        cache_set = factory.make_CacheSet(node=node)
        self.assertRaises(
            PermissionDenied,
            CacheSet.objects.get_cache_set_or_404,
            node.system_id,
            cache_set.id,
            user,
            NodePermission.edit,
        )

    def test_edit_returns_device_when_user_is_owner(self):
        user = factory.make_User()
        node = factory.make_Node(owner=user)
        cache_set = factory.make_CacheSet(node=node)
        self.assertEqual(
            cache_set.id,
            CacheSet.objects.get_cache_set_or_404(
                node.system_id, cache_set.id, user, NodePermission.edit
            ).id,
        )

    def test_admin_raises_PermissionDenied_when_user_requests_admin(self):
        user = factory.make_User()
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        self.assertRaises(
            PermissionDenied,
            CacheSet.objects.get_cache_set_or_404,
            node.system_id,
            cache_set.id,
            user,
            NodePermission.admin,
        )

    def test_admin_returns_device_when_admin(self):
        user = factory.make_admin()
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        self.assertEqual(
            cache_set.id,
            CacheSet.objects.get_cache_set_or_404(
                node.system_id, cache_set.id, user, NodePermission.admin
            ).id,
        )


class TestCacheSet(MAASServerTestCase):
    """Tests for the `CacheSet` model."""

    def test_name(self):
        node = factory.make_Node()
        cache_set_zero = factory.make_CacheSet(node=node)
        cache_set_one = factory.make_CacheSet(node=node)
        self.assertEqual("cache0", cache_set_zero.name)
        self.assertEqual("cache1", cache_set_one.name)

    def test_get_name(self):
        node = factory.make_Node()
        cache_set_zero = factory.make_CacheSet(node=node)
        cache_set_one = factory.make_CacheSet(node=node)
        self.assertEqual("cache0", cache_set_zero.get_name())
        self.assertEqual("cache1", cache_set_one.get_name())

    def test_get_node(self):
        node = factory.make_Node()
        cache_set = factory.make_CacheSet(node=node)
        self.assertEqual(node, cache_set.get_node())

    def test_get_filesystem(self):
        block_device = factory.make_PhysicalBlockDevice()
        cache_set = factory.make_CacheSet(block_device=block_device)
        self.assertEqual(
            block_device.get_effective_filesystem(), cache_set.get_filesystem()
        )

    def test_get_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        cache_set = factory.make_CacheSet(block_device=block_device)
        self.assertEqual(block_device, cache_set.get_device())

    def test_get_numa_nodes_indexes_only_own_device(self):
        block_device = factory.make_PhysicalBlockDevice()
        cache_set = factory.make_CacheSet(block_device=block_device)
        self.assertEqual(cache_set.get_numa_node_indexes(), [0])

    def test_get_numa_nodes_indexes_many_devices(self):
        node = factory.make_Node()
        numa_nodes = [
            node.default_numanode,
            factory.make_NUMANode(node=node),
            factory.make_NUMANode(node=node),
        ]
        block_devices = [
            factory.make_PhysicalBlockDevice(numa_node=numa_node)
            for numa_node in numa_nodes
        ]
        filesystems = [
            factory.make_Filesystem(
                fstype=FILESYSTEM_TYPE.LVM_PV, block_device=block_device
            )
            for block_device in block_devices
        ]
        fsgroup = factory.make_FilesystemGroup(
            node=node,
            filesystems=filesystems,
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
        )
        virtual_block_device = factory.make_VirtualBlockDevice(
            filesystem_group=fsgroup
        )
        cache_set = factory.make_CacheSet(block_device=virtual_block_device)
        self.assertEqual(cache_set.get_numa_node_indexes(), [0, 1, 2])
