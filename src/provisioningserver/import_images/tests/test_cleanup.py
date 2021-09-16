# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `cleanup` module."""


import os
from random import randint

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.import_images import cleanup


class TestCleanup(MAASTestCase):
    def make_snapshot_dir(self, storage):
        name = factory.make_name("snapshot")
        path = os.path.join(storage, name)
        os.mkdir(path)
        return path

    def make_cache_file(self, storage, link_count=0):
        cache_dir = os.path.join(storage, "cache")
        if not os.path.exists(cache_dir):
            os.mkdir(cache_dir)

        cache_file = factory.make_name("cache")
        cache_path = os.path.join(cache_dir, cache_file)
        open(cache_path, "wb").close()

        link_dir = os.path.join(storage, "links")
        if not os.path.exists(link_dir):
            os.mkdir(link_dir)

        for i in range(link_count):
            link_path = os.path.join(link_dir, "%s-%d" % (cache_file, i))
            os.link(cache_path, link_path)
        return cache_path

    def test_list_old_snapshots_returns_all(self):
        storage = self.make_dir()
        snapshots = [self.make_snapshot_dir(storage) for _ in range(3)]
        self.assertCountEqual(snapshots, cleanup.list_old_snapshots(storage))

    def test_list_old_snapshots_returns_all_but_current_directory(self):
        storage = self.make_dir()
        snapshots = [self.make_snapshot_dir(storage) for _ in range(3)]
        current_snapshot = self.make_snapshot_dir(storage)
        os.symlink(current_snapshot, os.path.join(storage, "current"))
        self.assertCountEqual(snapshots, cleanup.list_old_snapshots(storage))

    def test_cleanup_snapshots_removes_all_old_snapshots(self):
        storage = self.make_dir()
        snapshots = [self.make_snapshot_dir(storage) for _ in range(3)]
        current_snapshot = self.make_snapshot_dir(storage)
        os.symlink(current_snapshot, os.path.join(storage, "current"))
        cleanup.cleanup_snapshots(storage)
        remaining_snapshots = [
            snapshot for snapshot in snapshots if os.path.exists(snapshot)
        ]
        self.assertEqual([], remaining_snapshots)

    def test_list_unused_cache_files_returns_empty(self):
        storage = self.make_dir()
        self.assertEqual([], cleanup.list_unused_cache_files(storage))

    def test_list_unused_cache_files_returns_all_files_nlink_equal_one(self):
        storage = self.make_dir()
        cache_nlink_1 = [self.make_cache_file(storage) for _ in range(3)]
        for _ in range(3):
            self.make_cache_file(storage, link_count=randint(1, 3))
        self.assertCountEqual(
            cache_nlink_1, cleanup.list_unused_cache_files(storage)
        )

    def test_cleanup_cache_removes_all_files_nlink_equal_one(self):
        storage = self.make_dir()
        for _ in range(3):
            self.make_cache_file(storage)
        cache_nlink_greater_than_1 = [
            self.make_cache_file(storage, link_count=randint(1, 3))
            for _ in range(3)
        ]
        cleanup.cleanup_cache(storage)
        cache_dir = os.path.join(storage, "cache")
        remaining_cache = [
            os.path.join(cache_dir, filename)
            for filename in os.listdir(cache_dir)
            if os.path.isfile(os.path.join(cache_dir, filename))
        ]
        self.assertCountEqual(cache_nlink_greater_than_1, remaining_cache)

    def test_cleanup_snapshots_and_cache_calls(self):
        storage = self.make_dir()
        mock_snapshots = self.patch_autospec(cleanup, "cleanup_snapshots")
        mock_cache = self.patch_autospec(cleanup, "cleanup_cache")
        cleanup.cleanup_snapshots_and_cache(storage)
        self.assertThat(mock_snapshots, MockCalledOnceWith(storage))
        self.assertThat(mock_cache, MockCalledOnceWith(storage))
