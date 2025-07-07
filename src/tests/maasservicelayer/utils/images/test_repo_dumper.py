# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
from unittest.mock import MagicMock, patch, sentinel

import pytest
from structlog.testing import capture_logs

from maasservicelayer.utils.images.boot_image_mapping import BootImageMapping
from maasservicelayer.utils.images.repo_dumper import (
    clean_up_repo_item,
    RepoDumper,
    validate_product,
)
from maastesting.factory import factory
from tests.fixtures.factories.boot_sources import make_image_spec


class TestValidateProduct:
    def test_ignores_random(self):
        assert validate_product({}, factory.make_name("product_name"))

    def test_validates_ubuntu(self):
        assert validate_product(
            {"os": "ubuntu"},
            "com.ubuntu.maas.daily:v%d:boot:%s:%s:%s"
            % (
                random.choice([2, 3]),
                factory.make_name("version"),
                factory.make_name("arch"),
                factory.make_name("sub_arch"),
            ),
        )

    def test_validates_ubuntu_core(self):
        assert validate_product(
            {"os": "ubuntu-core"},
            "com.ubuntu.maas.daily:v4:%s:%s:%s:%s"
            % (
                factory.make_name("version"),
                factory.make_name("arch"),
                factory.make_name("gadget"),
                factory.make_name("channel"),
            ),
        )

    def test_rejects_unknown_ubuntu_version(self):
        assert not validate_product(
            {"os": "ubuntu"},
            "com.ubuntu.maas.daily:v%d:boot:%s:%s:%s"
            % (
                random.randint(4, 100),
                factory.make_name("version"),
                factory.make_name("arch"),
                factory.make_name("sub_arch"),
            ),
        )

    def test_validates_ubuntu_with_platform(self):
        assert validate_product(
            {"os": "ubuntu"},
            "com.ubuntu.maas.daily:v3+platform:boot:%s:%s:%s"
            % (
                factory.make_name("version"),
                factory.make_name("arch"),
                factory.make_name("sub_arch"),
            ),
        )

    def test_rejects_ubuntu_with_v4_platform(self):
        assert not validate_product(
            {"os": "ubuntu"},
            "com.ubuntu.maas.daily:v4+platform:boot:%s:%s:%s"
            % (
                factory.make_name("version"),
                factory.make_name("arch"),
                factory.make_name("sub_arch"),
            ),
        )

    def test_rejects_ubuntu_with_any_other_suffix(self):
        assert not validate_product(
            {"os": "ubuntu"},
            "com.ubuntu.maas.daily:v3%s:boot:%s:%s:%s"
            % (
                factory.make_name("suffix"),
                factory.make_name("version"),
                factory.make_name("arch"),
                factory.make_name("sub_arch"),
            ),
        )

    def test_validates_bootloaders(self):
        acceptable_bootloaders = [
            {"os": "pxelinux", "arch": "i386", "bootloader-type": "pxe"},
            {
                "os": "grub-efi-signed",
                "arch": "amd64",
                "bootloader-type": "uefi",
            },
            {"os": "grub-efi", "arch": "arm64", "bootloader-type": "uefi"},
            {
                "os": "grub-ieee1275",
                "arch": "ppc64el",
                "bootloader-type": "open-firmware",
            },
        ]
        for bootloader in acceptable_bootloaders:
            product_name = "com.ubuntu.maas.daily:1:{}:{}:{}".format(
                bootloader["os"],
                bootloader["bootloader-type"],
                bootloader["arch"],
            )
            assert validate_product(bootloader, product_name), (
                f"Failed to validate {product_name}"
            )

    def test_rejects_unknown_bootloader_version(self):
        version = random.randint(2, 100)
        product_name = "com.ubuntu.maas.daily:%d:pxelinux:pxe:i386" % version
        assert not validate_product(
            {"bootloader-type": factory.make_name("bootloader-type")},
            product_name,
        )

    def test_rejects_unknown_bootloader(self):
        bootloader = {
            "os": factory.make_name("os"),
            "arch": factory.make_name("arch"),
            "bootloader-type": factory.make_name("bootloader_type"),
        }
        product_name = "com.ubuntu.maas.daily:1:{}:{}:{}".format(
            bootloader["os"],
            bootloader["bootloader-type"],
            bootloader["arch"],
        )
        assert not validate_product(bootloader, product_name)


class TestRepoDumper:
    def make_item(
        self,
        os: str | None = None,
        release: str | None = None,
        version: str | None = None,
        arch: str | None = None,
        subarch: str | None = None,
        subarches: list[str] | None = None,
        label: str | None = None,
        bootloader_type: str | None = None,
    ):
        if os is None:
            os = factory.make_name("os")
        if release is None:
            release = factory.make_name("release")
        if version is None:
            version = factory.make_name("version")
        if arch is None:
            arch = factory.make_name("arch")
        if subarch is None:
            subarch = factory.make_name("subarch")
        if subarches is None:
            subarches = [factory.make_name("subarch") for _ in range(3)]
        if subarch not in subarches:
            subarches.append(subarch)
        if label is None:
            label = factory.make_name("label")
        item = {
            "content_id": factory.make_name("content_id"),
            "product_name": factory.make_name("product_name"),
            "version_name": factory.make_name("version_name"),
            "path": factory.make_name("path"),
            "os": os,
            "release": release,
            "version": version,
            "arch": arch,
            "subarch": subarch,
            "subarches": ",".join(subarches),
            "label": label,
        }
        if bootloader_type is not None:
            item["bootloader-type"] = bootloader_type
        if os == "ubuntu-core":
            item["gadget_snap"] = factory.make_name("gadget_snap")
            item["kernel_snap"] = factory.make_name("kernel_snap")
        return item, clean_up_repo_item(item)

    @patch("maasservicelayer.utils.images.repo_dumper.products_exdata")
    def test_insert_item_adds_item_per_subarch(
        self,
        mock_products_exdata: MagicMock,
    ) -> None:
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)
        subarches = [factory.make_name("subarch") for _ in range(3)]
        item, _ = self.make_item(subarch=subarches.pop(), subarches=subarches)

        mock_products_exdata.return_value = item

        dumper.insert_item(
            sentinel.data,
            sentinel.src,
            sentinel.target,
            (
                factory.make_name("product_name"),
                factory.make_name("product_version"),
            ),
            sentinel.contentsource,
        )
        image_specs = {
            make_image_spec(
                os=item["os"],
                release=item["release"],
                arch=item["arch"],
                subarch=subarch,
                label=item["label"],
            )
            for subarch in subarches
        }

        assert image_specs == boot_images_dict.mapping.keys()

    @patch("maasservicelayer.utils.images.repo_dumper.products_exdata")
    def test_insert_item_sets_compat_item_specific_to_subarch(
        self,
        mock_products_exdata: MagicMock,
    ) -> None:
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)
        subarches = [factory.make_name("subarch") for _ in range(5)]
        compat_subarch = subarches.pop()
        item, _ = self.make_item(subarch=subarches.pop(), subarches=subarches)
        second_item, compat_item = self.make_item(
            os=item["os"],
            release=item["release"],
            arch=item["arch"],
            subarch=compat_subarch,
            subarches=[compat_subarch],
            label=item["label"],
        )

        mock_products_exdata.side_effect = [
            item,
            second_item,
        ]

        for _ in range(2):
            dumper.insert_item(
                sentinel.data,
                sentinel.src,
                sentinel.target,
                (
                    factory.make_name("product_name"),
                    factory.make_name("product_version"),
                ),
                sentinel.contentsource,
            )
        image_spec = make_image_spec(
            os=item["os"],
            release=item["release"],
            arch=item["arch"],
            subarch=compat_subarch,
            label=item["label"],
        )

        assert compat_item == boot_images_dict.mapping[image_spec]

    @patch("maasservicelayer.utils.images.repo_dumper.products_exdata")
    def test_insert_item_sets_generic_to_release_item_for_hwe_letter(
        self,
        mock_products_exdata: MagicMock,
    ) -> None:
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)
        os = "ubuntu"
        release = "precise"
        arch = "amd64"
        label = "release"
        hwep_subarch = "hwe-p"
        hwep_subarches = ["generic", "hwe-p"]
        hwes_subarch = "hwe-s"
        hwes_subarches = ["generic", "hwe-p", "hwe-s"]
        hwep_item, compat_item = self.make_item(
            os=os,
            release=release,
            arch=arch,
            subarch=hwep_subarch,
            subarches=hwep_subarches,
            label=label,
        )
        hwes_item, _ = self.make_item(
            os=os,
            release=release,
            arch=arch,
            subarch=hwes_subarch,
            subarches=hwes_subarches,
            label=label,
        )

        mock_products_exdata.side_effect = [
            hwep_item,
            hwes_item,
        ]

        for _ in range(2):
            dumper.insert_item(
                {"os": "ubuntu"},
                sentinel.src,
                sentinel.target,
                (
                    "com.ubuntu.maas.daily:v3:boot:12.04:amd64:hwe-p",
                    factory.make_name("product_version"),
                ),
                sentinel.contentsource,
            )
        image_spec = make_image_spec(
            os=os, release=release, arch=arch, subarch="generic", label=label
        )

        assert compat_item == boot_images_dict.mapping[image_spec]

    @patch("maasservicelayer.utils.images.repo_dumper.products_exdata")
    def test_insert_item_sets_generic_to_release_item_for_hwe_version(
        self,
        mock_products_exdata: MagicMock,
    ) -> None:
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)
        os = "ubuntu"
        release = "xenial"
        arch = "amd64"
        label = "release"
        hwep_subarch = "hwe-16.04"
        hwep_subarches = ["generic", "hwe-16.04", "hwe-16.10"]
        hwes_subarch = "hwe-16.10"
        hwes_subarches = ["generic", "hwe-16.04", "hwe-16.10"]
        hwep_item, compat_item = self.make_item(
            os=os,
            release=release,
            arch=arch,
            subarch=hwep_subarch,
            subarches=hwep_subarches,
            label=label,
        )
        hwes_item, _ = self.make_item(
            os=os,
            release=release,
            arch=arch,
            subarch=hwes_subarch,
            subarches=hwes_subarches,
            label=label,
        )

        mock_products_exdata.side_effect = [
            hwep_item,
            hwes_item,
        ]

        for _ in range(2):
            dumper.insert_item(
                {"os": "ubuntu"},
                sentinel.src,
                sentinel.target,
                (
                    "com.ubuntu.maas.daily:v3:boot:12.04:amd64:hwe-p",
                    factory.make_name("product_version"),
                ),
                sentinel.contentsource,
            )
        image_spec = make_image_spec(
            os=os, release=release, arch=arch, subarch="generic", label=label
        )

        assert compat_item == boot_images_dict.mapping[image_spec]

    @patch("maasservicelayer.utils.images.repo_dumper.products_exdata")
    def test_insert_item_sets_release_to_bootloader_type(
        self,
        mock_products_exdata: MagicMock,
    ) -> None:
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)
        item, _ = self.make_item(
            arch="amd64", bootloader_type="uefi", os="grub-efi-signed"
        )

        mock_products_exdata.return_value = item

        dumper.insert_item(
            {
                "bootloader_type": "uefi",
                "os": "grub-efi-signed",
                "arch": "amd64",
            },
            sentinel.src,
            sentinel.target,
            (
                "com.ubuntu.maas.daily:1:grub-efi-signed:uefi:amd64",
                factory.make_name("product_version"),
            ),
            sentinel.contentsource,
        )
        image_specs = {
            make_image_spec(
                os=item["os"],
                release="uefi",
                arch=item["arch"],
                subarch=subarch,
                kflavor="bootloader",
                label=item["label"],
            )
            for subarch in item["subarches"].split(",")
        }

        assert image_specs == boot_images_dict.mapping.keys()

    @patch("maasservicelayer.utils.images.repo_dumper.products_exdata")
    def test_insert_item_validates(
        self,
        mock_products_exdata: MagicMock,
    ) -> None:
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)
        item, _ = self.make_item(os="ubuntu")

        mock_products_exdata.return_value = item

        dumper.insert_item(
            {"os": "ubuntu"},
            sentinel.src,
            sentinel.target,
            (
                factory.make_name("product_name"),
                factory.make_name("product_version"),
            ),
            sentinel.contentsource,
        )

        assert set() == boot_images_dict.mapping.keys()

    @patch("maasservicelayer.utils.images.repo_dumper.products_exdata")
    def test_insert_item_doesnt_validate_when_instructed(
        self,
        mock_products_exdata: MagicMock,
    ) -> None:
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict, validate_products=False)
        item, _ = self.make_item(os="ubuntu")

        mock_products_exdata.return_value = item

        dumper.insert_item(
            {"os": "ubuntu"},
            sentinel.src,
            sentinel.target,
            (
                factory.make_name("product_name"),
                factory.make_name("product_version"),
            ),
            sentinel.contentsource,
        )
        image_specs = {
            make_image_spec(
                os=item["os"],
                release=item["release"],
                arch=item["arch"],
                subarch=subarch,
                label=item["label"],
            )
            for subarch in item["subarches"].split(",")
        }

        assert image_specs == boot_images_dict.mapping.keys()

    @patch("maasservicelayer.utils.images.repo_dumper.BasicMirrorWriter.sync")
    def test_sync_does_propagate_ioerror(
        self,
        mock_mirror_writer_sync: MagicMock,
    ) -> None:
        io_error = factory.make_exception_type(bases=(IOError,))

        mock_mirror_writer_sync.side_effect = io_error()

        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)

        with capture_logs() as logs:
            with pytest.raises(io_error):
                dumper.sync(sentinel.reader, sentinel.path)

            assert "I/O error while syncing boot images" in logs[0]["event"]
