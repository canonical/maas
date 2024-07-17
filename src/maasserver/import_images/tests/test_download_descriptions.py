# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `download_descriptions` module."""


import logging
import random
from unittest.mock import ANY, call, Mock, sentinel

from fixtures import FakeLogger

from maasserver.import_images import download_descriptions
from maasserver.import_images.boot_image_mapping import BootImageMapping
from maasserver.import_images.download_descriptions import (
    clean_up_repo_item,
    RepoDumper,
    validate_product,
)
from maasserver.import_images.testing.factory import (
    make_image_spec,
    set_resource,
)
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestValidateProduct(MAASTestCase):
    """Tests for `validate_product`."""

    def test_ignores_random(self):
        self.assertTrue(
            validate_product({}, factory.make_name("product_name"))
        )

    def test_validates_ubuntu(self):
        self.assertTrue(
            validate_product(
                {"os": "ubuntu"},
                "com.ubuntu.maas.daily:v%d:boot:%s:%s:%s"
                % (
                    random.choice([2, 3]),
                    factory.make_name("version"),
                    factory.make_name("arch"),
                    factory.make_name("sub_arch"),
                ),
            )
        )

    def test_validates_ubuntu_core(self):
        self.assertTrue(
            validate_product(
                {"os": "ubuntu-core"},
                "com.ubuntu.maas.daily:v4:%s:%s:%s:%s"
                % (
                    factory.make_name("version"),
                    factory.make_name("arch"),
                    factory.make_name("gadget"),
                    factory.make_name("channel"),
                ),
            )
        )

    def test_rejects_unknown_ubuntu_version(self):
        self.assertFalse(
            validate_product(
                {"os": "ubuntu"},
                "com.ubuntu.maas.daily:v%d:boot:%s:%s:%s"
                % (
                    random.randint(4, 100),
                    factory.make_name("version"),
                    factory.make_name("arch"),
                    factory.make_name("sub_arch"),
                ),
            )
        )

    def test_validates_ubuntu_with_platform(self):
        self.assertTrue(
            validate_product(
                {"os": "ubuntu"},
                "com.ubuntu.maas.daily:v3+platform:boot:%s:%s:%s"
                % (
                    factory.make_name("version"),
                    factory.make_name("arch"),
                    factory.make_name("sub_arch"),
                ),
            )
        )

    def test_rejects_ubuntu_with_v4_platform(self):
        self.assertFalse(
            validate_product(
                {"os": "ubuntu"},
                "com.ubuntu.maas.daily:v4+platform:boot:%s:%s:%s"
                % (
                    factory.make_name("version"),
                    factory.make_name("arch"),
                    factory.make_name("sub_arch"),
                ),
            )
        )

    def test_rejects_ubuntu_with_any_other_suffix(self):
        self.assertFalse(
            validate_product(
                {"os": "ubuntu"},
                "com.ubuntu.maas.daily:v3%s:boot:%s:%s:%s"
                % (
                    factory.make_name("suffix"),
                    factory.make_name("version"),
                    factory.make_name("arch"),
                    factory.make_name("sub_arch"),
                ),
            )
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
            self.assertTrue(
                validate_product(bootloader, product_name),
                "Failed to validate %s" % product_name,
            )

    def test_rejects_unknown_bootloader_version(self):
        version = random.randint(2, 100)
        product_name = "com.ubuntu.maas.daily:%d:pxelinux:pxe:i386" % version
        self.assertFalse(
            validate_product(
                {"bootloader-type": factory.make_name("bootloader-type")},
                product_name,
            )
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
        self.assertFalse(validate_product(bootloader, product_name))


class TestValuePassesFilterList(MAASTestCase):
    """Tests for `value_passes_filter_list`."""

    def test_nothing_passes_empty_list(self):
        self.assertFalse(
            download_descriptions.value_passes_filter_list(
                [], factory.make_name("value")
            )
        )

    def test_unmatched_value_does_not_pass(self):
        self.assertFalse(
            download_descriptions.value_passes_filter_list(
                [factory.make_name("filter")], factory.make_name("value")
            )
        )

    def test_matched_value_passes(self):
        value = factory.make_name("value")
        self.assertTrue(
            download_descriptions.value_passes_filter_list([value], value)
        )

    def test_value_passes_if_matched_anywhere_in_filter(self):
        value = factory.make_name("value")
        self.assertTrue(
            download_descriptions.value_passes_filter_list(
                [
                    factory.make_name("filter"),
                    value,
                    factory.make_name("filter"),
                ],
                value,
            )
        )

    def test_any_value_passes_asterisk(self):
        self.assertTrue(
            download_descriptions.value_passes_filter_list(
                ["*"], factory.make_name("value")
            )
        )


class TestValuePassesFilter(MAASTestCase):
    """Tests for `value_passes_filter`."""

    def test_unmatched_value_does_not_pass(self):
        self.assertFalse(
            download_descriptions.value_passes_filter(
                factory.make_name("filter"), factory.make_name("value")
            )
        )

    def test_matching_value_passes(self):
        value = factory.make_name("value")
        self.assertTrue(
            download_descriptions.value_passes_filter(value, value)
        )

    def test_any_value_matches_asterisk(self):
        self.assertTrue(
            download_descriptions.value_passes_filter(
                "*", factory.make_name("value")
            )
        )


class TestImagePassesFilter(MAASTestCase):
    """Tests for `image_passes_filter`."""

    def make_filter_from_image(self, image_spec=None):
        """Create a filter dict that matches the given `ImageSpec`.

        If `image_spec` is not given, creates a random value.
        """
        if image_spec is None:
            image_spec = make_image_spec()
        return {
            "os": image_spec.os,
            "arches": [image_spec.arch],
            "subarches": [image_spec.subarch],
            "release": image_spec.release,
            "labels": [image_spec.label],
        }

    def test_any_image_passes_none_filter(self):
        os, arch, subarch, _, release, label = make_image_spec()
        self.assertTrue(
            download_descriptions.image_passes_filter(
                None, os, arch, subarch, release, label
            )
        )

    def test_any_image_passes_empty_filter(self):
        os, arch, subarch, kflavor, release, label = make_image_spec()
        self.assertTrue(
            download_descriptions.image_passes_filter(
                [], os, arch, subarch, release, label
            )
        )

    def test_image_passes_matching_filter(self):
        image = make_image_spec()
        self.assertTrue(
            download_descriptions.image_passes_filter(
                [self.make_filter_from_image(image)],
                image.os,
                image.arch,
                image.subarch,
                image.release,
                image.label,
            )
        )

    def test_image_does_not_pass_nonmatching_filter(self):
        image = make_image_spec()
        self.assertFalse(
            download_descriptions.image_passes_filter(
                [self.make_filter_from_image()],
                image.os,
                image.arch,
                image.subarch,
                image.release,
                image.label,
            )
        )

    def test_image_passes_if_one_filter_matches(self):
        image = make_image_spec()
        self.assertTrue(
            download_descriptions.image_passes_filter(
                [
                    self.make_filter_from_image(),
                    self.make_filter_from_image(image),
                    self.make_filter_from_image(),
                ],
                image.os,
                image.arch,
                image.subarch,
                image.release,
                image.label,
            )
        )

    def test_filter_checks_release(self):
        image = make_image_spec()
        self.assertFalse(
            download_descriptions.image_passes_filter(
                [
                    self.make_filter_from_image(
                        image._replace(
                            release=factory.make_name("other-release")
                        )
                    )
                ],
                image.os,
                image.arch,
                image.subarch,
                image.release,
                image.label,
            )
        )

    def test_filter_checks_arches(self):
        image = make_image_spec()
        self.assertFalse(
            download_descriptions.image_passes_filter(
                [
                    self.make_filter_from_image(
                        image._replace(arch=factory.make_name("other-arch"))
                    )
                ],
                image.os,
                image.arch,
                image.subarch,
                image.release,
                image.label,
            )
        )

    def test_filter_checks_subarches(self):
        image = make_image_spec()
        self.assertFalse(
            download_descriptions.image_passes_filter(
                [
                    self.make_filter_from_image(
                        image._replace(
                            subarch=factory.make_name("other-subarch")
                        )
                    )
                ],
                image.os,
                image.arch,
                image.subarch,
                image.release,
                image.label,
            )
        )

    def test_filter_checks_labels(self):
        image = make_image_spec()
        self.assertFalse(
            download_descriptions.image_passes_filter(
                [
                    self.make_filter_from_image(
                        image._replace(label=factory.make_name("other-label"))
                    )
                ],
                image.os,
                image.arch,
                image.subarch,
                image.release,
                image.label,
            )
        )


class TestBootMerge(MAASTestCase):
    """Tests for `boot_merge`."""

    def test_integrates(self):
        # End-to-end scenario for boot_merge: start with an empty boot
        # resources dict, and receive one resource from Simplestreams.
        total_resources = BootImageMapping()
        resources_from_repo = set_resource()
        download_descriptions.boot_merge(total_resources, resources_from_repo)
        # Since we started with an empty dict, the result contains the same
        # item that we got from Simplestreams, and nothing else.
        self.assertEqual(resources_from_repo.mapping, total_resources.mapping)

    def test_obeys_filters(self):
        filters = [
            {
                "os": factory.make_name("os"),
                "arches": [factory.make_name("other-arch")],
                "subarches": [factory.make_name("other-subarch")],
                "release": factory.make_name("other-release"),
                "label": [factory.make_name("other-label")],
            }
        ]
        total_resources = BootImageMapping()
        resources_from_repo = set_resource()
        download_descriptions.boot_merge(
            total_resources, resources_from_repo, filters=filters
        )
        self.assertEqual({}, total_resources.mapping)

    def test_does_not_overwrite_existing_entry(self):
        image = make_image_spec()
        total_resources = set_resource(
            resource="Original resource", image_spec=image
        )
        original_resources = total_resources.mapping.copy()
        resources_from_repo = set_resource(
            resource="New resource", image_spec=image
        )
        download_descriptions.boot_merge(total_resources, resources_from_repo)
        self.assertEqual(original_resources, total_resources.mapping)


class TestRepoDumper(MAASTestCase):
    """Tests for `RepoDumper`."""

    def make_item(
        self,
        os=None,
        release=None,
        version=None,
        arch=None,
        subarch=None,
        subarches=None,
        label=None,
        bootloader_type=None,
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

    def test_insert_item_adds_item_per_subarch(self):
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)
        subarches = [factory.make_name("subarch") for _ in range(3)]
        item, _ = self.make_item(subarch=subarches.pop(), subarches=subarches)
        self.patch(download_descriptions, "products_exdata").return_value = (
            item
        )
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
        self.assertEqual(image_specs, boot_images_dict.mapping.keys())

    def test_insert_item_sets_compat_item_specific_to_subarch(self):
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
        self.patch(download_descriptions, "products_exdata").side_effect = [
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
        self.assertEqual(compat_item, boot_images_dict.mapping[image_spec])

    def test_insert_item_sets_generic_to_release_item_for_hwe_letter(self):
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
        self.patch(download_descriptions, "products_exdata").side_effect = [
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
        self.assertEqual(compat_item, boot_images_dict.mapping[image_spec])

    def test_insert_item_sets_generic_to_release_item_for_hwe_version(self):
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
        self.patch(download_descriptions, "products_exdata").side_effect = [
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
        self.assertEqual(compat_item, boot_images_dict.mapping[image_spec])

    def test_insert_item_sets_release_to_bootloader_type(self):
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)
        item, _ = self.make_item(
            arch="amd64", bootloader_type="uefi", os="grub-efi-signed"
        )
        self.patch(download_descriptions, "products_exdata").return_value = (
            item
        )
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
        self.assertEqual(image_specs, boot_images_dict.mapping.keys())

    def test_insert_item_validates(self):
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)
        item, _ = self.make_item(os="ubuntu")
        self.patch(download_descriptions, "products_exdata").return_value = (
            item
        )
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
        self.assertEqual(set(), boot_images_dict.mapping.keys())

    def test_insert_item_doesnt_validate_when_instructed(self):
        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict, validate_products=False)
        item, _ = self.make_item(os="ubuntu")
        self.patch(download_descriptions, "products_exdata").return_value = (
            item
        )
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
        self.assertEqual(image_specs, boot_images_dict.mapping.keys())

    def test_sync_does_propagate_ioerror(self):
        io_error = factory.make_exception_type(bases=(IOError,))

        mock_sync = self.patch(download_descriptions.BasicMirrorWriter, "sync")
        mock_sync.side_effect = io_error()

        boot_images_dict = BootImageMapping()
        dumper = RepoDumper(boot_images_dict)

        with FakeLogger("maas.import-images", level=logging.INFO) as maaslog:
            self.assertRaises(
                io_error, dumper.sync, sentinel.reader, sentinel.path
            )
        self.assertIn("I/O error while syncing boot images.", maaslog.output)


class TestDownloadImageDescriptionsUserAgent(MAASTestCase):
    """Tests for user agent string with `download_image_descriptions.`"""

    def test_doesnt_pass_user_agent_when_not_set(self):
        mock_UrlMirrorReader = self.patch(
            download_descriptions, "UrlMirrorReader"
        )
        self.patch(download_descriptions.RepoDumper, "sync")
        path = factory.make_url()
        download_descriptions.download_image_descriptions(path)
        mock_UrlMirrorReader.assert_called_once_with(path, policy=ANY)

    def test_passes_user_agent(self):
        mock_UrlMirrorReader = self.patch(
            download_descriptions, "UrlMirrorReader"
        )
        self.patch(download_descriptions.RepoDumper, "sync")
        path = factory.make_url()
        user_agent = factory.make_name("agent")
        download_descriptions.download_image_descriptions(
            path, user_agent=user_agent
        )
        mock_UrlMirrorReader.assert_called_once_with(
            path, policy=ANY, user_agent=user_agent
        )

    def test_doesnt_pass_user_agenton_fallback(self):
        mock_UrlMirrorReader = self.patch(
            download_descriptions, "UrlMirrorReader"
        )
        mock_UrlMirrorReader.side_effect = [TypeError(), Mock()]
        self.patch(download_descriptions.RepoDumper, "sync")
        path = factory.make_url()
        user_agent = factory.make_name("agent")
        download_descriptions.download_image_descriptions(
            path, user_agent=user_agent
        )
        mock_UrlMirrorReader.assert_has_calls(
            [
                call(path, policy=ANY, user_agent=user_agent),
                call(path, policy=ANY),
            ]
        )
