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
        json_version = bootloader_product_list.dict()

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
        json_version = ubuntu_product_list.dict()

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
        json_version = centos_product_list.dict()

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
