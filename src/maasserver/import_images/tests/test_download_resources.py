# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.import_images.download_resources`."""

import hashlib
import os
import random
import tarfile
from unittest import mock

from django.utils import timezone
from simplestreams.contentsource import ChecksummingContentSource
from simplestreams.objectstores import FileStore

from maasserver.import_images import download_resources
from maasserver.import_images.product_mapping import ProductMapping
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.config import DEFAULT_IMAGES_URL
from provisioningserver.utils.fs import tempdir


class MockDateTime(mock.MagicMock):
    """A class for faking datetimes."""

    _utcnow = timezone.now()

    @classmethod
    def now(cls):
        return cls._utcnow


class TestDownloadAllBootResources(MAASTestCase):
    """Tests for `download_all_boot_resources`()."""

    def test_returns_snapshot_path(self):
        self.patch(download_resources, "timezone", MockDateTime)
        storage_path = self.make_dir()
        expected_path = os.path.join(
            storage_path,
            "snapshot-%s" % MockDateTime._utcnow.strftime("%Y%m%d-%H%M%S"),
        )
        self.assertEqual(
            expected_path,
            download_resources.download_all_boot_resources(
                sources=[], storage_path=storage_path, product_mapping=None
            ),
        )

    def test_calls_download_boot_resources(self):
        self.patch(download_resources, "timezone", MockDateTime)
        storage_path = self.make_dir()
        snapshot_path = download_resources.compose_snapshot_path(storage_path)
        cache_path = os.path.join(storage_path, "cache")
        file_store = FileStore(cache_path)
        source = {
            "url": "http://example.com",
            "keyring": self.make_file("keyring"),
        }
        product_mapping = ProductMapping()
        fake = self.patch(download_resources, "download_boot_resources")
        download_resources.download_all_boot_resources(
            sources=[source],
            storage_path=storage_path,
            product_mapping=product_mapping,
            store=file_store,
        )
        fake.assert_called_once_with(
            source["url"],
            file_store,
            snapshot_path,
            product_mapping,
            keyring_file=source["keyring"],
        )


class TestDownloadBootResources(MAASTestCase):
    """Tests for `download_boot_resources()`."""

    def test_syncs_repo(self):
        fake_sync = self.patch(download_resources.RepoWriter, "sync")
        storage_path = self.make_dir()
        snapshot_path = self.make_dir()
        cache_path = os.path.join(storage_path, "cache")
        file_store = FileStore(cache_path)
        source_url = DEFAULT_IMAGES_URL

        download_resources.download_boot_resources(
            source_url, file_store, snapshot_path, None, None
        )
        self.assertEqual(1, len(fake_sync.mock_calls))


class TestComposeSnapshotPath(MAASTestCase):
    """Tests for `compose_snapshot_path`()."""

    def test_returns_path_under_storage_path(self):
        self.patch(download_resources, "timezone", MockDateTime)
        storage_path = self.make_dir()
        expected_path = os.path.join(
            storage_path,
            "snapshot-%s" % MockDateTime._utcnow.strftime("%Y%m%d-%H%M%S"),
        )
        self.assertEqual(
            expected_path,
            download_resources.compose_snapshot_path(storage_path),
        )


class TestExtractArchiveTar(MAASTestCase):
    """Tests for `extract_archive_Tar`()."""

    def get_file_info(self, filename):
        sha256 = hashlib.sha256()
        size = 0
        with open(filename, "rb") as f:
            for chunk in iter(lambda: f.read(2**15), b""):
                sha256.update(chunk)
                size += len(chunk)
        return sha256.hexdigest(), size

    def make_tar_xz(self, path):
        tar_xz_path = os.path.join(
            path, factory.make_name("archive") + ".tar.xz"
        )
        files = {}
        with tarfile.open(tar_xz_path, "w:xz") as tar:
            with tempdir() as tmp:
                for _ in range(3):
                    f = factory.make_file(tmp)
                    tar_path = os.path.basename(f)
                    tar.add(f, tar_path)
                    files[tar_path] = self.get_file_info(f)
                subdir = os.path.join(tmp, "subdir")
                os.makedirs(subdir)
                for _ in range(3):
                    f = factory.make_file(subdir)
                    tar_path = f[len(tmp) + 1 :]
                    tar.add(f, tar_path)
                    files[tar_path] = self.get_file_info(f)
        return tar_xz_path, files

    def test_extracts_files(self):
        with tempdir() as cache_dir:
            store = FileStore(cache_dir)
            tar_xz, files = self.make_tar_xz(cache_dir)
            sha256, size = self.get_file_info(tar_xz)
            checksums = {"sha256": sha256}
            with open(tar_xz, "rb") as f:
                content_source = ChecksummingContentSource(f, checksums, size)
                cached_files = download_resources.extract_archive_tar(
                    store,
                    os.path.basename(tar_xz),
                    sha256,
                    checksums,
                    size,
                    content_source,
                )
                for f, info in files.items():
                    cached_file = os.path.join(cache_dir, f"{f}-{sha256}")
                    expected_cached_file = (cached_file, f)
                    self.assertIn(expected_cached_file, cached_files)
                    self.assertTrue(os.path.exists(cached_file))
                    self.assertEqual(info, self.get_file_info(cached_file))

    def test_returns_files_from_cache(self):
        with tempdir() as cache_dir:
            store = FileStore(cache_dir)
            tar_xz, files = self.make_tar_xz(cache_dir)
            sha256, size = self.get_file_info(tar_xz)
            checksums = {"sha256": sha256}
            with open(tar_xz, "rb") as f:
                content_source = ChecksummingContentSource(f, checksums, size)
                download_resources.extract_archive_tar(
                    store,
                    os.path.basename(tar_xz),
                    sha256,
                    checksums,
                    size,
                    content_source,
                )
                mocked_tar = self.patch(download_resources.tarfile, "open")
                cached_files = download_resources.extract_archive_tar(
                    store,
                    os.path.basename(tar_xz),
                    sha256,
                    checksums,
                    size,
                    content_source,
                )
                mocked_tar.assert_not_called()
                for f, info in files.items():  # noqa: B007
                    cached_file = os.path.join(cache_dir, f"{f}-{sha256}")
                    expected_cached_file = (cached_file, f)
                    self.assertIn(expected_cached_file, cached_files)


class TestRepoWriter(MAASTestCase):
    """Tests for `RepoWriter`."""

    def make_product(self, **kwargs):
        return {
            "content_id": "maas:v2:download",
            "product_name": factory.make_string(),
            "version_name": timezone.now().strftime("%Y%m%d"),
            "sha256": factory.make_name("sha256"),
            "size": random.randint(2, 2**16),
            "ftype": factory.make_name("ftype"),
            "path": "/path/to/%s" % factory.make_name("filename"),
            "os": factory.make_name("os"),
            "release": factory.make_name("release"),
            "arch": factory.make_name("arch"),
            "label": factory.make_name("label"),
            **kwargs,
        }

    def test_inserts_archive(self):
        product_mapping = ProductMapping()
        subarch = factory.make_name("subarch")
        product = self.make_product(ftype="archive.tar.xz", subarch=subarch)
        product_mapping.add(product, subarch)
        repo_writer = download_resources.RepoWriter(
            None, None, product_mapping
        )
        self.patch(
            download_resources, "products_exdata"
        ).return_value = product
        # Prevent MAAS from trying to actually write the file.
        mock_extract_archive_tar = self.patch(
            download_resources, "extract_archive_tar"
        )
        mock_link_resources = self.patch(download_resources, "link_resources")
        # We only need to provide the product as the other fields are only used
        # when writing the actual files to disk.
        repo_writer.insert_item(product, None, None, None, None)
        # None is used for the store and the content source as we're not
        # writing anything to disk.
        mock_extract_archive_tar.assert_called_once_with(
            None,
            os.path.basename(product["path"]),
            product["sha256"],
            {"sha256": product["sha256"]},
            product["size"],
            None,
        )
        # links are mocked out by the mock_insert_file above.
        mock_link_resources.assert_called_once_with(
            snapshot_path=None,
            links=mock.ANY,
            osystem=product["os"],
            arch=product["arch"],
            release=product["release"],
            label=product["label"],
            subarches={subarch},
            bootloader_type=None,
        )

    def test_inserts_file(self):
        product_mapping = ProductMapping()
        subarch = factory.make_name("subarch")
        product = self.make_product(subarch=subarch)
        product_mapping.add(product, subarch)
        repo_writer = download_resources.RepoWriter(
            None, None, product_mapping
        )
        self.patch(
            download_resources, "products_exdata"
        ).return_value = product
        # Prevent MAAS from trying to actually write the file.
        mock_insert_file = self.patch(download_resources, "insert_file")
        mock_link_resources = self.patch(download_resources, "link_resources")
        # We only need to provide the product as the other fields are only used
        # when writing the actual files to disk.
        repo_writer.insert_item(product, None, None, None, None)
        # None is used for the store and the content source as we're not
        # writing anything to disk.
        mock_insert_file.assert_called_once_with(
            None,
            os.path.basename(product["path"]),
            product["sha256"],
            {"sha256": product["sha256"]},
            product["size"],
            None,
        )
        # links are mocked out by the mock_insert_file above.
        mock_link_resources.assert_called_once_with(
            snapshot_path=None,
            links=mock.ANY,
            osystem=product["os"],
            arch=product["arch"],
            release=product["release"],
            label=product["label"],
            subarches={subarch},
            bootloader_type=None,
        )

    def test_inserts_rolling_links(self):
        product_mapping = ProductMapping()
        product = self.make_product(subarch="hwe-16.04", rolling=True)
        product_mapping.add(product, "hwe-16.04")
        repo_writer = download_resources.RepoWriter(
            None, None, product_mapping
        )
        self.patch(
            download_resources, "products_exdata"
        ).return_value = product
        # Prevent MAAS from trying to actually write the file.
        mock_insert_file = self.patch(download_resources, "insert_file")
        mock_link_resources = self.patch(download_resources, "link_resources")
        # We only need to provide the product as the other fields are only used
        # when writing the actual files to disk.
        repo_writer.insert_item(product, None, None, None, None)
        # None is used for the store and the content source as we're not
        # writing anything to disk.
        mock_insert_file.assert_called_once_with(
            None,
            os.path.basename(product["path"]),
            product["sha256"],
            {"sha256": product["sha256"]},
            product["size"],
            None,
        )
        # links are mocked out by the mock_insert_file above.
        mock_link_resources.assert_called_once_with(
            snapshot_path=None,
            links=mock.ANY,
            osystem=product["os"],
            arch=product["arch"],
            release=product["release"],
            label=product["label"],
            subarches={"hwe-16.04", "hwe-rolling"},
            bootloader_type=None,
        )

    def test_only_creates_links_for_its_own_subarch(self):
        # Regression test for LP:1656425
        product_name = factory.make_name("product_name")
        version_name = factory.make_name("version_name")
        product_mapping = ProductMapping()
        for subarch in [
            "hwe-p",
            "hwe-q",
            "hwe-r",
            "hwe-s",
            "hwe-t",
            "hwe-u",
            "hwe-v",
            "hwe-w",
            "ga-16.04",
        ]:
            product = self.make_product(
                product_name=product_name,
                version_name=version_name,
                subarch=subarch,
            )
            product_mapping.add(product, subarch)
        repo_writer = download_resources.RepoWriter(
            None, None, product_mapping
        )
        self.patch(
            download_resources, "products_exdata"
        ).return_value = product
        # Prevent MAAS from trying to actually write the file.
        mock_insert_file = self.patch(download_resources, "insert_file")
        mock_link_resources = self.patch(download_resources, "link_resources")
        # We only need to provide the product as the other fields are only used
        # when writing the actual files to disk.
        repo_writer.insert_item(product, None, None, None, None)
        # None is used for the store and the content source as we're not
        # writing anything to disk.
        mock_insert_file.assert_called_once_with(
            None,
            os.path.basename(product["path"]),
            product["sha256"],
            {"sha256": product["sha256"]},
            product["size"],
            None,
        )
        # links are mocked out by the mock_insert_file above.
        mock_link_resources.assert_called_once_with(
            snapshot_path=None,
            links=mock.ANY,
            osystem=product["os"],
            arch=product["arch"],
            release=product["release"],
            label=product["label"],
            subarches={"ga-16.04"},
            bootloader_type=None,
        )

    def test_inserts_generic_link_for_generic_ga_kflavor(self):
        product_mapping = ProductMapping()
        product = self.make_product(subarch="ga-16.04", kflavor="generic")
        product_mapping.add(product, "ga-16.04")
        repo_writer = download_resources.RepoWriter(
            None, None, product_mapping
        )
        self.patch(
            download_resources, "products_exdata"
        ).return_value = product
        # Prevent MAAS from trying to actually write the file.
        mock_insert_file = self.patch(download_resources, "insert_file")
        mock_link_resources = self.patch(download_resources, "link_resources")
        # We only need to provide the product as the other fields are only used
        # when writing the actual files to disk.
        repo_writer.insert_item(product, None, None, None, None)
        # None is used for the store and the content source as we're not
        # writing anything to disk.
        (
            mock_insert_file.assert_called_once_with(
                None,
                os.path.basename(product["path"]),
                product["sha256"],
                {"sha256": product["sha256"]},
                product["size"],
                None,
            ),
        )
        # links are mocked out by the mock_insert_file above.
        mock_link_resources.assert_called_once_with(
            snapshot_path=None,
            links=mock.ANY,
            osystem=product["os"],
            arch=product["arch"],
            release=product["release"],
            label=product["label"],
            subarches={"ga-16.04", "generic"},
            bootloader_type=None,
        )

    def test_inserts_no_generic_link_for_generic_non_ga_kflavor(self):
        # Regression test for LP:1749246
        product_mapping = ProductMapping()
        product = self.make_product(subarch="hwe-16.04", kflavor="generic")
        product_mapping.add(product, "hwe-16.04")
        repo_writer = download_resources.RepoWriter(
            None, None, product_mapping
        )
        self.patch(
            download_resources, "products_exdata"
        ).return_value = product
        # Prevent MAAS from trying to actually write the file.
        mock_insert_file = self.patch(download_resources, "insert_file")
        mock_link_resources = self.patch(download_resources, "link_resources")
        # We only need to provide the product as the other fields are only used
        # when writing the actual files to disk.
        repo_writer.insert_item(product, None, None, None, None)
        # None is used for the store and the content source as we're not
        # writing anything to disk.
        mock_insert_file.assert_called_once_with(
            None,
            os.path.basename(product["path"]),
            product["sha256"],
            {"sha256": product["sha256"]},
            product["size"],
            None,
        )
        # links are mocked out by the mock_insert_file above.
        mock_link_resources.assert_called_once_with(
            snapshot_path=None,
            links=mock.ANY,
            osystem=product["os"],
            arch=product["arch"],
            release=product["release"],
            label=product["label"],
            subarches={"hwe-16.04"},
            bootloader_type=None,
        )

    def test_inserts_generic_link_for_generic_kflavor_old_hwe_style_ga(self):
        # Regression test for LP:1768323
        product_mapping = ProductMapping()
        product = self.make_product(
            subarch="hwe-p", kflavor="generic", release="precise"
        )
        product_mapping.add(product, "hwe-p")
        repo_writer = download_resources.RepoWriter(
            None, None, product_mapping
        )
        self.patch(
            download_resources, "products_exdata"
        ).return_value = product
        # Prevent MAAS from trying to actually write the file.
        mock_insert_file = self.patch(download_resources, "insert_file")
        mock_link_resources = self.patch(download_resources, "link_resources")
        # We only need to provide the product as the other fields are only used
        # when writing the actual files to disk.
        repo_writer.insert_item(product, None, None, None, None)
        # None is used for the store and the content source as we're not
        # writing anything to disk.
        mock_insert_file.assert_called_once_with(
            None,
            os.path.basename(product["path"]),
            product["sha256"],
            {"sha256": product["sha256"]},
            product["size"],
            None,
        )
        # links are mocked out by the mock_insert_file above.
        mock_link_resources.assert_called_once_with(
            snapshot_path=None,
            links=mock.ANY,
            osystem=product["os"],
            arch=product["arch"],
            release=product["release"],
            label=product["label"],
            subarches={"hwe-p", "generic"},
            bootloader_type=None,
        )


class TestLinkResources(MAASTestCase):
    """Tests for `LinkResources`()."""

    def make_files(self, path):
        tag = factory.make_name("tag")
        links = []
        for _ in range(3):
            filename = factory.make_name("filename")
            filename_with_tag = f"{filename}-{tag}"
            factory.make_file(location=path, name=filename_with_tag)
            filepath = os.path.join(path, filename_with_tag)
            links.append((filepath, filename))
        subdir = factory.make_name("subdir")
        os.makedirs(os.path.join(path, subdir))
        for _ in range(3):
            filename = os.path.join(subdir, factory.make_name("filename"))
            filename_with_tag = f"{filename}-{tag}"
            factory.make_file(location=path, name=filename_with_tag)
            filepath = os.path.join(path, filename_with_tag)
            links.append((filepath, filename))
        return tag, links

    def test_links_resources(self):
        with tempdir() as snapshot_path:
            tag, links = self.make_files(snapshot_path)
            osystem = factory.make_name("osystem")
            arch = factory.make_name("arch")
            release = factory.make_name("release")
            label = factory.make_name("label")
            subarches = [factory.make_name("subarch") for _ in range(3)]

            download_resources.link_resources(
                snapshot_path,
                links,
                osystem,
                arch,
                release,
                label,
                subarches,
                None,
            )

            for subarch in subarches:
                for cached_file, logical_name in links:
                    cached_file_path = os.path.join(snapshot_path, cached_file)
                    logical_name_path = os.path.join(
                        snapshot_path,
                        osystem,
                        arch,
                        subarch,
                        release,
                        label,
                        logical_name,
                    )
                    self.assertTrue(os.path.exists(cached_file_path))
                    self.assertTrue(os.path.exists(logical_name_path))

    def test_links_bootloader(self):
        with tempdir() as snapshot_path:
            tag, links = self.make_files(snapshot_path)
            osystem = factory.make_name("osystem")
            arch = factory.make_name("arch")
            release = factory.make_name("release")
            label = factory.make_name("label")
            subarches = [factory.make_name("subarch")]
            bootloader_type = factory.make_name("bootloader-type")

            download_resources.link_resources(
                snapshot_path,
                links,
                osystem,
                arch,
                release,
                label,
                subarches,
                bootloader_type,
            )

            for cached_file, logical_name in links:  # noqa: B007
                cached_file_path = os.path.join(snapshot_path, cached_file)
                logical_name_path = os.path.join(
                    snapshot_path, "bootloader", bootloader_type, arch
                )
                self.assertTrue(os.path.exists(cached_file_path))
                self.assertTrue(os.path.exists(logical_name_path))

    def test_bootloader_only_allows_one_subarch(self):
        with tempdir() as snapshot_path:
            tag, links = self.make_files(snapshot_path)
            osystem = factory.make_name("osystem")
            arch = factory.make_name("arch")
            release = factory.make_name("release")
            label = factory.make_name("label")
            subarches = [factory.make_name("subarch") for _ in range(3)]
            bootloader_type = factory.make_name("bootloader-type")

            self.assertRaises(
                AssertionError,
                download_resources.link_resources,
                snapshot_path,
                links,
                osystem,
                arch,
                release,
                label,
                subarches,
                bootloader_type,
            )
