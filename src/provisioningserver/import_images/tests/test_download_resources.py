# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.import_images.download_resources`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os
from datetime import datetime
from maastesting.testcase import MAASTestCase
from base64 import b64encode
from provisioningserver.import_images import download_resources
from provisioningserver.import_images.product_mapping import ProductMapping
from maastesting.matchers import MockCalledWith
from testtools.matchers import FileContains
from simplestreams.objectstores import FileStore
import mock


class MockDateTime(mock.MagicMock):
    """A class for faking datetimes."""

    _utcnow = datetime.utcnow()

    @classmethod
    def utcnow(cls):
        return cls._utcnow


class TestDownloadAllBootResources(MAASTestCase):
    """Tests for `download_all_boot_resources`()."""

    def test_accepts_keyring_data_in_sources(self):
        keyring_data = b64encode("A keyring!")
        source = {
            'path': 'http://example.com',
            'keyring_data': keyring_data,
            'selections': [{
                'release': 'trusty',
                'arches': ['amd64'],
                'subarches': ['generic'],
                'labels': ['release'],
                }]
            }
        self.patch(download_resources, 'datetime', MockDateTime)
        storage_path = self.make_dir()
        snapshot_path = download_resources.compose_snapshot_path(
            storage_path)
        cache_path = os.path.join(storage_path, 'cache')
        ubuntu_path = os.path.join(snapshot_path, 'ubuntu')
        file_store = FileStore(cache_path)

        fake = self.patch(download_resources, 'download_boot_resources')
        download_resources.download_all_boot_resources(
            sources=[source], storage_path=storage_path,
            store=file_store, product_mapping=None)

        self.assertThat(
            fake,
            MockCalledWith(
                source['path'], file_store, ubuntu_path, None,
                keyring_file=None, keyring_data=keyring_data))

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
        ubuntu_path = os.path.join(snapshot_path, 'ubuntu')
        cache_path = os.path.join(storage_path, 'cache')
        file_store = FileStore(cache_path)
        source = {
            'path': 'http://example.com',
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
                source['path'], file_store, ubuntu_path, product_mapping,
                keyring_file=source['keyring'], keyring_data=None))


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

    def test_writes_keyring_data(self):
        # Stop the sync from actually downloading everything.
        self.patch(download_resources.RepoWriter, 'sync')
        fake_write_keyring = self.patch(download_resources, 'write_keyring')

        storage_path = self.make_dir()
        snapshot_path = self.make_dir()
        cache_path = os.path.join(storage_path, 'cache')
        file_store = FileStore(cache_path)
        source_url = "http://%s" % self.getUniqueString()
        keyring_data = b64encode(b"A keyring! My kingdom for a keyring!")

        keyring_path = self.make_dir()
        self.patch(
            download_resources.tempfile,
            'mkdtemp').return_value = keyring_path
        download_resources.download_boot_resources(
            source_url, file_store, snapshot_path, product_mapping=None,
            keyring_data=keyring_data)
        expected_keyring_path = os.path.join(
            keyring_path,
            download_resources.calculate_keyring_name(source_url))
        self.assertThat(
            fake_write_keyring,
            MockCalledWith(expected_keyring_path, keyring_data))


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


class TestWriteKeyring(MAASTestCase):
    """Tests for `write_keyring().`"""

    def test_writes_keyring_to_file(self):
        keyring_data = b"A keyring! My kingdom for a keyring!"
        keyring_path = os.path.join(self.make_dir(), "a-keyring-file")
        download_resources.write_keyring(
            keyring_path, b64encode(keyring_data))
        self.assertTrue(os.path.exists(keyring_path))
        self.assertThat(keyring_path, FileContains(keyring_data))


class TestCalculateKeyringName(MAASTestCase):
    """Tests for `calculate_keyring_name()`."""

    def test_creates_name_from_url(self):
        parts = [self.getUniqueString() for i in range(1,5)]
        source_url = "http://example.com/%s/" % "/".join(parts)
        expected_keyring_name = "example.com-%s.gpg" % "-".join(parts)
        self.assertEqual(
            expected_keyring_name,
            download_resources.calculate_keyring_name(source_url))
