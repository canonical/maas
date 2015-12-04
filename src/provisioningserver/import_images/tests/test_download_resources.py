# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.import_images.download_resources`."""

__all__ = []

from datetime import datetime
import os

from maastesting.matchers import MockCalledWith
from maastesting.testcase import MAASTestCase
import mock
from provisioningserver.import_images import download_resources
from provisioningserver.import_images.product_mapping import ProductMapping
from simplestreams.objectstores import FileStore


class MockDateTime(mock.MagicMock):
    """A class for faking datetimes."""

    _utcnow = datetime.utcnow()

    @classmethod
    def utcnow(cls):
        return cls._utcnow


class TestDownloadAllBootResources(MAASTestCase):
    """Tests for `download_all_boot_resources`()."""

    def test_returns_snapshot_path(self):
        self.patch(download_resources, 'datetime', MockDateTime)
        storage_path = self.make_dir()
        expected_path = os.path.join(
            storage_path,
            'snapshot-%s' % MockDateTime._utcnow.strftime('%Y%m%d-%H%M%S'))
        self.assertEqual(
            expected_path,
            download_resources.download_all_boot_resources(
                sources=[], storage_path=storage_path,
                product_mapping=None))

    def test_calls_download_boot_resources(self):
        self.patch(download_resources, 'datetime', MockDateTime)
        storage_path = self.make_dir()
        snapshot_path = download_resources.compose_snapshot_path(
            storage_path)
        cache_path = os.path.join(storage_path, 'cache')
        file_store = FileStore(cache_path)
        source = {
            'url': 'http://example.com',
            'keyring': self.make_file("keyring"),
            }
        product_mapping = ProductMapping()
        fake = self.patch(download_resources, 'download_boot_resources')
        download_resources.download_all_boot_resources(
            sources=[source], storage_path=storage_path,
            product_mapping=product_mapping, store=file_store)
        self.assertThat(
            fake,
            MockCalledWith(
                source['url'], file_store, snapshot_path, product_mapping,
                keyring_file=source['keyring']))


class TestDownloadBootResources(MAASTestCase):
    """Tests for `download_boot_resources()`."""

    def test_syncs_repo(self):
        fake_sync = self.patch(download_resources.RepoWriter, 'sync')
        storage_path = self.make_dir()
        snapshot_path = self.make_dir()
        cache_path = os.path.join(storage_path, 'cache')
        file_store = FileStore(cache_path)
        source_url = "http://maas.ubuntu.com/images/ephemeral-v2/releases/"

        download_resources.download_boot_resources(
            source_url, file_store, snapshot_path, None, None)
        self.assertEqual(1, len(fake_sync.mock_calls))


class TestComposeSnapshotPath(MAASTestCase):
    """Tests for `compose_snapshot_path`()."""

    def test_returns_path_under_storage_path(self):
        self.patch(download_resources, 'datetime', MockDateTime)
        storage_path = self.make_dir()
        expected_path = os.path.join(
            storage_path,
            'snapshot-%s' % MockDateTime._utcnow.strftime('%Y%m%d-%H%M%S'))
        self.assertEqual(
            expected_path,
            download_resources.compose_snapshot_path(storage_path))
