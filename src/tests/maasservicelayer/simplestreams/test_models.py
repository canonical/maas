# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json

import pytest

from maasservicelayer.simplestreams.models import (
    BootloaderFile,
    BootloaderProduct,
    BootloaderVersion,
    ImageFile,
    MultiFileImageVersion,
    MultiFileProduct,
    SimpleStreamsBootloaderProductList,
    SimpleStreamsIndexList,
    SimpleStreamsMultiFileProductList,
    SimpleStreamsProductListFactory,
    SimpleStreamsSingleFileProductList,
    SingleFileImageVersion,
    SingleFileProduct,
)
from tests.fixtures import get_test_data_file

INDEX_LIST = json.loads(get_test_data_file("simplestreams_index.json"))

BOOTLOADER_PRODUCTS = json.loads(
    get_test_data_file("simplestreams_bootloaders.json")
)

UBUNTU_PRODUCTS = json.loads(get_test_data_file("simplestreams_ubuntu.json"))

CENTOS_PRODUCTS = json.loads(get_test_data_file("simplestreams_centos.json"))


class TestIndexList:
    def test_from_json(self):
        index_list = SimpleStreamsIndexList(**INDEX_LIST)
        assert len(index_list.indexes) == 3
        bootloader_index = index_list.indexes[0]
        assert len(bootloader_index.products) == 5
        centos_index = index_list.indexes[1]
        assert len(centos_index.products) == 2
        ubuntu_index = index_list.indexes[2]
        assert len(ubuntu_index.products) == 4


class TestBootloaderProductList:
    def test_from_json(self):
        bootloader_product_list = SimpleStreamsBootloaderProductList(
            **BOOTLOADER_PRODUCTS
        )
        assert len(bootloader_product_list.products) == 5
        product = bootloader_product_list.products[0]
        assert isinstance(product, BootloaderProduct)
        assert len(product.versions) == 2
        version = product.versions[0]
        assert isinstance(version, BootloaderVersion)
        files = version.get_downloadable_files()
        assert len(files) == 2
        for file in files:
            assert isinstance(file, BootloaderFile)

    def test_serialize_deserialize(self):
        bootloader_product_list = SimpleStreamsBootloaderProductList(
            **BOOTLOADER_PRODUCTS
        )
        json_version = bootloader_product_list.model_dump()

        SimpleStreamsBootloaderProductList(**json_version)


class TestMultiFileProductList:
    def test_from_json(self):
        ubuntu_product_list = SimpleStreamsMultiFileProductList(
            **UBUNTU_PRODUCTS
        )
        assert len(ubuntu_product_list.products) == 4
        product = ubuntu_product_list.products[0]
        assert isinstance(product, MultiFileProduct)
        assert len(product.versions) == 2
        version = product.versions[0]
        assert isinstance(version, MultiFileImageVersion)
        files = version.get_downloadable_files()
        assert len(files) == 3
        for file in files:
            assert isinstance(file, ImageFile)

    def test_serialize_deserialize(self):
        ubuntu_product_list = SimpleStreamsMultiFileProductList(
            **UBUNTU_PRODUCTS
        )
        json_version = ubuntu_product_list.model_dump()

        SimpleStreamsMultiFileProductList(**json_version)


class TestSingleFileProductList:
    def test_from_json(self):
        centos_product_list = SimpleStreamsSingleFileProductList(
            **CENTOS_PRODUCTS
        )
        assert len(centos_product_list.products) == 2
        product = centos_product_list.products[0]
        assert isinstance(product, SingleFileProduct)
        assert len(product.versions) == 2
        version = product.versions[0]
        assert isinstance(version, SingleFileImageVersion)
        files = version.get_downloadable_files()
        assert len(files) == 1
        for file in files:
            assert isinstance(file, ImageFile)

    def test_serialize_deserialize(self):
        centos_product_list = SimpleStreamsSingleFileProductList(
            **CENTOS_PRODUCTS
        )
        json_version = centos_product_list.model_dump()

        SimpleStreamsSingleFileProductList(**json_version)


class TestProductListFactory:
    def test_produce(self):
        product_lists = []
        for data in (BOOTLOADER_PRODUCTS, UBUNTU_PRODUCTS, CENTOS_PRODUCTS):
            product_lists.append(SimpleStreamsProductListFactory.produce(data))

        assert len(product_lists) == 3
        assert isinstance(product_lists[0], SimpleStreamsBootloaderProductList)
        assert isinstance(product_lists[1], SimpleStreamsMultiFileProductList)
        assert isinstance(product_lists[2], SimpleStreamsSingleFileProductList)

    def test_raises_error_invalid_data(self):
        with pytest.raises(ValueError) as e:
            SimpleStreamsProductListFactory.produce({})

        assert (
            str(e.value)
            == "Data does not match any known SimpleStreams model."
        )


class TestMissingOptionalFields:
    """Test to ensure model validation doesn't break when optional fields are not passed."""

    def test_image_file_with_missing_kpackage(self):
        file_data = {
            "ftype": "tar.gz",
            "path": "ubuntu/20.04/squashfs",
            "sha256": "def456",
            "size": 2048,
        }
        image_file = ImageFile(**file_data)
        assert image_file.kpackage is None

    def test_multifile_version_with_missing_optional_fields(self):
        version_data = {
            "version_name": "20240101",
            "items": {
                "boot-initrd": {
                    "ftype": "tar.gz",
                    "path": "ubuntu/initrd",
                    "sha256": "aaa111",
                    "size": 512,
                },
                "boot-kernel": {
                    "ftype": "tar.gz",
                    "path": "ubuntu/kernel",
                    "sha256": "bbb222",
                    "size": 1024,
                },
                "manifest": {
                    "ftype": "json",
                    "path": "ubuntu/manifest.json",
                    "sha256": "ccc333",
                    "size": 256,
                },
                "squashfs": {
                    "ftype": "squashfs",
                    "path": "ubuntu/squashfs",
                    "sha256": "ddd444",
                    "size": 4096,
                },
            },
        }
        version = MultiFileImageVersion(**version_data)
        assert version.support_eol is None
        assert version.support_esm_eol is None
        assert version.root_image_gz is None
        assert version.squashfs is not None

    def test_multifile_product_with_missing_optional_fields(self):
        product_data = {
            "product_name": "com.ubuntu.maas:v3:ubuntu:20.04:amd64",
            "arch": "amd64",
            "label": "Ubuntu 20.04",
            "os": "ubuntu",
            "release": "focal",
            "release_title": "Ubuntu 20.04 LTS",
            "subarch": "generic",
            "subarches": "generic",
            "version": "20.04",
            "versions": [],
        }
        product = MultiFileProduct(**product_data)
        assert product.kflavor is None
        assert product.krel is None
        assert product.release_codename is None
        assert product.support_eol is None
