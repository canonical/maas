# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

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

INDEX_LIST = {
    "format": "index:1.0",
    "index": {
        "com.ubuntu.maas:stable:1:bootloader-download": {
            "datatype": "image-ids",
            "format": "products:1.0",
            "path": "streams/v1/com.ubuntu.maas:stable:1:bootloader-download.sjson",
            "products": [
                "com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64",
                "com.ubuntu.maas.stable:1:grub-efi:uefi:arm64",
                "com.ubuntu.maas.stable:1:grub-ieee1275:open-firmware:ppc64el",
                "com.ubuntu.maas.stable:1:pxelinux:pxe:amd64",
                "com.ubuntu.maas.stable:1:pxelinux:pxe:i386",
            ],
            "updated": "Wed, 25 Jun 2025 11:01:49 +0000",
        },
        "com.ubuntu.maas:stable:centos-bases-download": {
            "datatype": "image-ids",
            "format": "products:1.0",
            "path": "streams/v1/com.ubuntu.maas:stable:centos-bases-download.sjson",
            "products": [
                "com.ubuntu.maas.stable:centos-bases:7.0:amd64",
                "com.ubuntu.maas.stable:centos-bases:8:amd64",
            ],
            "updated": "Wed, 25 Jun 2025 11:01:49 +0000",
        },
        "com.ubuntu.maas:stable:v3:download": {
            "datatype": "image-ids",
            "format": "products:1.0",
            "path": "streams/v1/com.ubuntu.maas:stable:v3:download.sjson",
            "products": [
                "com.ubuntu.maas.stable:v3:boot:24.04:amd64:ga-24.04",
                "com.ubuntu.maas.stable:v3:boot:24.04:amd64:ga-24.04-lowlatency",
                "com.ubuntu.maas.stable:v3:boot:24.04:amd64:hwe-24.04",
            ],
            "updated": "Wed, 25 Jun 2025 11:01:49 +0000",
        },
    },
    "updated": "Wed, 25 Jun 2025 11:01:49 +0000",
}

BOOTLOADER_PRODUCTS = {
    "content_id": "com.ubuntu.maas:stable:1:bootloader-download",
    "datatype": "image-ids",
    "format": "products:1.0",
    "products": {
        "com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64": {
            "arch": "amd64",
            "arches": "amd64",
            "bootloader-type": "uefi",
            "label": "stable",
            "os": "grub-efi-signed",
            "versions": {
                "20210819.0": {
                    "items": {
                        "grub2-signed": {
                            "ftype": "archive.tar.xz",
                            "path": "bootloaders/uefi/amd64/20210819.0/grub2-signed.tar.xz",
                            "sha256": "9d4a3a826ed55c46412613d2f7caf3185da4d6b18f35225f4f6a5b86b2bccfe3",
                            "size": 375316,
                            "src_package": "grub2-signed",
                            "src_release": "focal",
                            "src_version": "1.167.2+2.04-1ubuntu44.2",
                        },
                        "shim-signed": {
                            "ftype": "archive.tar.xz",
                            "path": "bootloaders/uefi/amd64/20210819.0/shim-signed.tar.xz",
                            "sha256": "07b42d0aa2540b6999c726eacf383e2c8f172378c964bdefab6d71410e2b72db",
                            "size": 322336,
                            "src_package": "shim-signed",
                            "src_release": "focal",
                            "src_version": "1.40.7+15.4-0ubuntu9",
                        },
                    }
                },
                "20221029.0": {
                    "items": {
                        "grub2-signed": {
                            "ftype": "archive.tar.xz",
                            "path": "bootloaders/uefi/amd64/20221029.0/grub2-signed.tar.xz",
                            "sha256": "505b50ca2f7ac189da478696acddba23466fb8ae98a2be3d29c69184546d113d",
                            "size": 375908,
                            "src_package": "grub2-signed",
                            "src_release": "focal",
                            "src_version": "1.173.2~20.04.1+2.04-1ubuntu47.4",
                        },
                        "shim-signed": {
                            "ftype": "archive.tar.xz",
                            "path": "bootloaders/uefi/amd64/20221029.0/shim-signed.tar.xz",
                            "sha256": "74cf7286febd0b29b33ef09362ddb443358df6722dd28c261fcd820591979333",
                            "size": 322268,
                            "src_package": "shim-signed",
                            "src_release": "focal",
                            "src_version": "1.40.7+15.4-0ubuntu9",
                        },
                    }
                },
            },
        }
    },
    "updated": "Thu, 26 Jun 2025 08:02:41 +0000",
}

UBUNTU_PRODUCTS = {
    "content_id": "com.ubuntu.maas:stable:v3:download",
    "datatype": "image-ids",
    "format": "products:1.0",
    "products": {
        "com.ubuntu.maas.stable:v3:boot:24.10:amd64:ga-24.10": {
            "arch": "amd64",
            "kflavor": "generic",
            "krel": "oracular",
            "label": "stable",
            "os": "ubuntu",
            "release": "oracular",
            "release_codename": "Oracular Oriole",
            "release_title": "24.10",
            "subarch": "ga-24.10",
            "subarches": "generic,hwe-p,hwe-q,hwe-r,hwe-s,hwe-t,hwe-u,hwe-v,hwe-w,ga-16.04,ga-16.10,ga-17.04,ga-17.10,ga-18.04,ga-18.10,ga-19.04,ga-19.10,ga-20.04,ga-20.10,ga-21.04,ga-21.10,ga-22.04,ga-22.10,ga-23.04,ga-23.10,ga-24.04,ga-24.10",
            "support_eol": "2025-07-10",
            "support_esm_eol": "2025-07-10",
            "version": "24.10",
            "versions": {
                "20250404": {
                    "items": {
                        "boot-initrd": {
                            "ftype": "boot-initrd",
                            "kpackage": "linux-generic",
                            "path": "oracular/amd64/20250404/ga-24.10/generic/boot-initrd",
                            "sha256": "e42de3a72d142498c2945e8b0e1b9bad2fc031a2224b7497ccaca66199b51f93",
                            "size": 75990212,
                        },
                        "boot-kernel": {
                            "ftype": "boot-kernel",
                            "kpackage": "linux-generic",
                            "path": "oracular/amd64/20250404/ga-24.10/generic/boot-kernel",
                            "sha256": "b2a29c2d269742933c15ed0ad48340ff4691261bdf0e6ba3c721dd15b835766d",
                            "size": 15440264,
                        },
                        "manifest": {
                            "ftype": "manifest",
                            "path": "oracular/amd64/20250404/squashfs.manifest",
                            "sha256": "5a5c81aebfc41adafb7db34d6f8022ab0084b1dddcfb8b2ff55f735ffd7a64fd",
                            "size": 17898,
                        },
                        "squashfs": {
                            "ftype": "squashfs",
                            "path": "oracular/amd64/20250404/squashfs",
                            "sha256": "201b7972f0f3b3bc5a345b85ed3a63688981c74b3fe52805edb2853fdbd70bbf",
                            "size": 272650240,
                        },
                    }
                },
                "20250409": {
                    "items": {
                        "boot-initrd": {
                            "ftype": "boot-initrd",
                            "kpackage": "linux-generic",
                            "path": "oracular/amd64/20250409/ga-24.10/generic/boot-initrd",
                            "sha256": "44464ab87925e26883ea380890dc1a001fabaf78415cdb900d1efed55df873a8",
                            "size": 75992073,
                        },
                        "boot-kernel": {
                            "ftype": "boot-kernel",
                            "kpackage": "linux-generic",
                            "path": "oracular/amd64/20250409/ga-24.10/generic/boot-kernel",
                            "sha256": "b2a29c2d269742933c15ed0ad48340ff4691261bdf0e6ba3c721dd15b835766d",
                            "size": 15440264,
                        },
                        "manifest": {
                            "ftype": "manifest",
                            "path": "oracular/amd64/20250409/squashfs.manifest",
                            "sha256": "4b37f913ed80b2bde7cd197092d8b6a896d8903ef4a4c6ab9eba243259bdad91",
                            "size": 17902,
                        },
                        "squashfs": {
                            "ftype": "squashfs",
                            "path": "oracular/amd64/20250409/squashfs",
                            "sha256": "65e7ff90d1c78f750673ccf76fcb70aab85861aa0b365d621711ef22582d5fde",
                            "size": 272662528,
                        },
                    }
                },
            },
        }
    },
    "updated": "Thu, 26 Jun 2025 08:02:41 +0000",
}

CENTOS_PRODUCTS = {
    "content_id": "com.ubuntu.maas:stable:centos-bases-download",
    "datatype": "image-ids",
    "format": "products:1.0",
    "products": {
        "com.ubuntu.maas.stable:centos-bases:7.0:amd64": {
            "arch": "amd64",
            "label": "stable",
            "os": "centos",
            "release": "centos70",
            "release_title": "CentOS 7",
            "subarch": "generic",
            "subarches": "generic",
            "support_eol": "2024-06-30",
            "version": "7.0",
            "versions": {
                "20240128_01": {
                    "items": {
                        "manifest": {
                            "ftype": "manifest",
                            "path": "centos/centos70/amd64/20240128_01/root-tgz.manifest",
                            "sha256": "1824770031fe2c6bb642ab0f3a7e6ffa58394072516ac453ebbe2c1377abd239",
                            "size": 10794,
                        },
                        "root-tgz": {
                            "ftype": "root-tgz",
                            "path": "centos/centos70/amd64/20240128_01/root-tgz",
                            "sha256": "e928234f396e4fc981e1bf59c8532c1d2c625957f2322190995c40ee50736394",
                            "size": 542934905,
                        },
                    }
                },
                "20240501_01": {
                    "items": {
                        "manifest": {
                            "ftype": "manifest",
                            "path": "centos/centos70/amd64/20240501_01/root-tgz.manifest",
                            "sha256": "08040c28df18cbba699233e7bd89e863559445767a30a79f5390b30c2dc884c6",
                            "size": 10794,
                        },
                        "root-tgz": {
                            "ftype": "root-tgz",
                            "path": "centos/centos70/amd64/20240501_01/root-tgz",
                            "sha256": "25aefa07a2e6cf562ec374048c9a641319e5fe2dadff09492f56de576a1681f1",
                            "size": 542980012,
                        },
                    }
                },
            },
        }
    },
    "updated": "Thu, 26 Jun 2025 08:02:41 +0000",
}


class TestIndexList:
    def test_from_json(self):
        index_list = SimpleStreamsIndexList(**INDEX_LIST)
        assert len(index_list.indexes) == 3
        bootloader_index = index_list.indexes[0]
        assert len(bootloader_index.products) == 5
        centos_index = index_list.indexes[1]
        assert len(centos_index.products) == 2
        ubuntu_index = index_list.indexes[2]
        assert len(ubuntu_index.products) == 3


class TestBootloaderProductList:
    def test_from_json(self):
        bootloader_product_list = SimpleStreamsBootloaderProductList(
            **BOOTLOADER_PRODUCTS
        )
        assert len(bootloader_product_list.products) == 1
        product = bootloader_product_list.products[0]
        assert isinstance(product, BootloaderProduct)
        assert len(product.versions) == 2
        version = product.versions[0]
        assert isinstance(version, BootloaderVersion)
        files = version.get_downloadable_files()
        assert len(files) == 2
        for file in files:
            assert isinstance(file, BootloaderFile)


class TestMultiFileProductList:
    def test_from_json(self):
        ubuntu_product_list = SimpleStreamsMultiFileProductList(
            **UBUNTU_PRODUCTS
        )
        assert len(ubuntu_product_list.products) == 1
        product = ubuntu_product_list.products[0]
        assert isinstance(product, MultiFileProduct)
        assert len(product.versions) == 2
        version = product.versions[0]
        assert isinstance(version, MultiFileImageVersion)
        files = version.get_downloadable_files()
        assert len(files) == 4
        for file in files:
            assert isinstance(file, ImageFile)


class TestSingleFileProductList:
    def test_from_json(self):
        centos_product_list = SimpleStreamsSingleFileProductList(
            **CENTOS_PRODUCTS
        )
        assert len(centos_product_list.products) == 1
        product = centos_product_list.products[0]
        assert isinstance(product, SingleFileProduct)
        assert len(product.versions) == 2
        version = product.versions[0]
        assert isinstance(version, SingleFileImageVersion)
        files = version.get_downloadable_files()
        assert len(files) == 2
        for file in files:
            assert isinstance(file, ImageFile)


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
