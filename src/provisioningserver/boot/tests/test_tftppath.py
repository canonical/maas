# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the tftppath module."""


import errno
import os.path
from unittest.mock import Mock

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.boot import tftppath
from provisioningserver.boot.tftppath import (
    compose_image_path,
    drill_down,
    extend_path,
    extract_image_params,
    extract_metadata,
    is_visible_subdir,
    list_boot_images,
    list_subdirs,
    maas_meta_last_modified,
)
from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.import_images.boot_image_mapping import (
    BootImageMapping,
)
from provisioningserver.import_images.helpers import ImageSpec
from provisioningserver.import_images.testing.factory import (
    make_image_spec,
    set_resource,
)
from provisioningserver.testing.boot_images import (
    make_boot_image_storage_params,
    make_image,
)
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.testing.os import make_osystem


class TestTFTPPath(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.tftproot = self.make_dir()
        self.useFixture(ClusterConfigurationFixture(tftp_root=self.tftproot))

    def make_image_dir(self, image_params, tftproot):
        """Fake a boot image matching `image_params` under `tftproot`."""
        image_dir = os.path.join(
            tftproot,
            compose_image_path(
                osystem=image_params["osystem"],
                arch=image_params["architecture"],
                subarch=image_params["subarchitecture"],
                release=image_params["release"],
                label=image_params["label"],
            ),
        )
        os.makedirs(image_dir)
        factory.make_file(image_dir, "linux")
        factory.make_file(image_dir, "initrd.gz")

    def make_meta_file(self, image_params, image_resource, tftproot):
        image = ImageSpec(
            os=image_params["osystem"],
            arch=image_params["architecture"],
            subarch=image_params["subarchitecture"],
            kflavor="generic",
            release=image_params["release"],
            label=image_params["label"],
        )
        mapping = BootImageMapping()
        mapping.setdefault(image, image_resource)
        maas_meta = mapping.dump_json()
        filepath = os.path.join(tftproot, "maas.meta")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(maas_meta)

    def test_maas_meta_last_modified_returns_modification_time(self):
        path = factory.make_file(self.tftproot, name="maas.meta")
        expected = os.path.getmtime(path)
        observed = maas_meta_last_modified(self.tftproot)
        self.assertEqual(expected, observed)

    def test_maas_meta_last_modified_returns_None_if_no_file(self):
        observed = maas_meta_last_modified(
            os.path.join(self.tftproot, "maas.meta")
        )
        self.assertIsNone(observed)

    def test_maas_meta_last_modified_reraises_non_ENOENT(self):
        path = factory.make_file(self.tftproot, name="maas.meta")
        oserror = OSError()
        oserror.errno = errno.E2BIG
        self.patch(os.path, "getmtime").side_effect = oserror
        self.assertRaises(OSError, maas_meta_last_modified, path)

    def test_compose_image_path_follows_storage_directory_layout(self):
        osystem = factory.make_name("osystem")
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        release = factory.make_name("release")
        label = factory.make_name("label")
        self.assertEqual(
            f"{osystem}/{arch}/{subarch}/{release}/{label}",
            compose_image_path(osystem, arch, subarch, release, label),
        )

    def test_compose_image_path_does_not_include_tftp_root(self):
        osystem = factory.make_name("osystem")
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        release = factory.make_name("release")
        label = factory.make_name("label")
        image_path = compose_image_path(osystem, arch, subarch, release, label)
        self.assertFalse(image_path.startswith(self.tftproot))

    def test_list_boot_images_copes_with_missing_directory(self):
        self.assertEqual([], list_boot_images(factory.make_string()))

    def test_list_boot_images_passes_on_other_exceptions(self):
        # OSError(EACCESS) is transmogrified, by Python itself, into
        # PermissionError. It's a subclass of OSError.
        error = OSError(errno.EACCES, "Deliberate error for testing.")
        self.patch(tftppath, "list_subdirs", Mock(side_effect=error))
        with self.assertRaisesRegex(
            PermissionError, "Deliberate error for testing."
        ):
            list_boot_images(factory.make_string())

    def test_list_boot_images_copes_with_empty_directory(self):
        self.assertEqual([], list_boot_images(self.tftproot))

    def test_list_boot_images_copes_with_unexpected_files(self):
        os.makedirs(os.path.join(self.tftproot, factory.make_name("empty")))
        factory.make_file(self.tftproot)
        self.assertEqual([], list_boot_images(self.tftproot))

    def test_list_boot_images_finds_boot_image(self):
        params = make_boot_image_storage_params()
        self.make_image_dir(params, self.tftproot)
        purposes = ["install", "commissioning", "xinstall"]
        make_osystem(self, params["osystem"], purposes)
        self.assertCountEqual(
            [make_image(params, purpose) for purpose in purposes],
            list_boot_images(self.tftproot),
        )

    def test_list_boot_images_enumerates_boot_images(self):
        purposes = ["install", "commissioning", "xinstall"]
        params = [make_boot_image_storage_params() for counter in range(3)]
        for param in params:
            self.make_image_dir(param, self.tftproot)
            make_osystem(self, param["osystem"], purposes)
        self.assertCountEqual(
            [
                make_image(param, purpose)
                for param in params
                for purpose in purposes
            ],
            list_boot_images(self.tftproot),
        )

    def test_list_boot_images_merges_maas_meta_data(self):
        params = make_boot_image_storage_params()
        self.make_image_dir(params, self.tftproot)
        # The required metadata is called "subarches" in maas.meta
        metadata = dict(subarches=factory.make_name("subarches"))
        self.make_meta_file(params, metadata, self.tftproot)
        purposes = ["install", "commissioning", "xinstall"]
        make_osystem(self, params["osystem"], purposes)
        # The API requires "supported_subarches".
        expected_metadata = dict(supported_subarches=metadata["subarches"])
        self.assertCountEqual(
            [
                make_image(params, purpose, expected_metadata)
                for purpose in purposes
            ],
            list_boot_images(self.tftproot),
        )

    def test_list_boot_images_empty_on_missing_osystems(self):
        params = [make_boot_image_storage_params() for counter in range(3)]
        for param in params:
            self.make_image_dir(param, self.tftproot)
        self.assertEqual([], list_boot_images(self.tftproot))

    def test_is_visible_subdir_ignores_regular_files(self):
        plain_file = self.make_file()
        self.assertFalse(
            is_visible_subdir(
                os.path.dirname(plain_file), os.path.basename(plain_file)
            )
        )

    def test_is_visible_subdir_ignores_hidden_directories(self):
        base_dir = self.make_dir()
        hidden_dir = factory.make_name(".")
        os.makedirs(os.path.join(base_dir, hidden_dir))
        self.assertFalse(is_visible_subdir(base_dir, hidden_dir))

    def test_is_visible_subdir_recognizes_subdirectory(self):
        base_dir = self.make_dir()
        subdir = factory.make_name("subdir")
        os.makedirs(os.path.join(base_dir, subdir))
        self.assertTrue(is_visible_subdir(base_dir, subdir))

    def test_list_subdirs_lists_empty_directory(self):
        self.assertEqual([], list_subdirs(self.make_dir()))

    def test_list_subdirs_lists_subdirs(self):
        base_dir = self.make_dir()
        factory.make_file(base_dir, factory.make_name("plain-file"))
        subdir = factory.make_name("subdir")
        os.makedirs(os.path.join(base_dir, subdir))
        self.assertEqual([subdir], list_subdirs(base_dir))

    def test_extend_path_finds_path_extensions(self):
        base_dir = self.make_dir()
        subdirs = [
            factory.make_name("subdir-%d" % counter) for counter in range(3)
        ]
        for subdir in subdirs:
            os.makedirs(os.path.join(base_dir, subdir))
        self.assertCountEqual(
            [[os.path.basename(base_dir), subdir] for subdir in subdirs],
            extend_path(
                os.path.dirname(base_dir), [os.path.basename(base_dir)]
            ),
        )

    def test_extend_path_builds_on_given_paths(self):
        base_dir = self.make_dir()
        lower_dir = factory.make_name("lower")
        subdir = factory.make_name("sub")
        os.makedirs(os.path.join(base_dir, lower_dir, subdir))
        self.assertEqual(
            [[lower_dir, subdir]], extend_path(base_dir, [lower_dir])
        )

    def test_extend_path_stops_if_no_subdirs_found(self):
        self.assertCountEqual([], extend_path(self.make_dir(), []))

    def test_drill_down_follows_directory_tree(self):
        base_dir = self.make_dir()
        lower_dir = factory.make_name("lower")
        os.makedirs(os.path.join(base_dir, lower_dir))
        subdirs = [
            factory.make_name("subdir-%d" % counter) for counter in range(3)
        ]
        for subdir in subdirs:
            os.makedirs(os.path.join(base_dir, lower_dir, subdir))
        self.assertCountEqual(
            [[lower_dir, subdir] for subdir in subdirs],
            drill_down(base_dir, [[lower_dir]]),
        )

    def test_drill_down_ignores_subdir_not_in_path(self):
        base_dir = self.make_dir()
        irrelevant_dir = factory.make_name("irrelevant")
        irrelevant_subdir = factory.make_name("subdir")
        relevant_dir = factory.make_name("relevant")
        relevant_subdir = factory.make_name("subdir")
        os.makedirs(os.path.join(base_dir, irrelevant_dir, irrelevant_subdir))
        os.makedirs(os.path.join(base_dir, relevant_dir, relevant_subdir))
        self.assertCountEqual(
            [[relevant_dir, relevant_subdir]],
            drill_down(base_dir, [[relevant_dir]]),
        )

    def test_drill_down_drops_paths_that_do_not_go_deep_enough(self):
        base_dir = self.make_dir()
        shallow_dir = factory.make_name("shallow")
        os.makedirs(os.path.join(base_dir, shallow_dir))
        deep_dir = factory.make_name("deep")
        subdir = factory.make_name("sub")
        os.makedirs(os.path.join(base_dir, deep_dir, subdir))
        self.assertEqual(
            [[deep_dir, subdir]],
            drill_down(base_dir, [[shallow_dir], [deep_dir]]),
        )

    def test_extract_metadata(self):
        resource = dict(
            subarches=factory.make_name("subarch"),
            other_item=factory.make_name("other"),
        )
        image = make_image_spec(kflavor="generic")
        mapping = set_resource(image_spec=image, resource=resource)
        metadata = mapping.dump_json()

        # Lack of consistency across maas in naming arch vs architecture
        # and subarch vs subarchitecture means I can't just do a simple
        # dict parameter expansion here.
        params = {
            "osystem": image.os,
            "architecture": image.arch,
            "subarchitecture": image.subarch,
            "release": image.release,
            "label": image.label,
        }
        extracted_data = extract_metadata(metadata, params)

        # We only expect the supported_subarches key from the resource data.
        expected = dict(supported_subarches=resource["subarches"])
        self.assertEqual(expected, extracted_data)

    def test_extract_metadata_handles_missing_subarch(self):
        resource = dict(other_item=factory.make_name("other"))
        image = make_image_spec()
        mapping = set_resource(image_spec=image, resource=resource)
        metadata = mapping.dump_json()

        # Lack of consistency across maas in naming arch vs architecture
        # and subarch vs subarchitecture means I can't just do a simple
        # dict parameter expansion here.
        params = {
            "osystem": image.os,
            "architecture": image.arch,
            "subarchitecture": image.subarch,
            "release": image.release,
            "label": image.label,
        }
        self.assertEqual({}, extract_metadata(metadata, params))

    def test_extract_metadata_parses_kflavor(self):
        resource = dict(
            subarches=factory.make_name("subarch"),
            other_item=factory.make_name("other"),
        )
        image = make_image_spec(
            subarch="hwe-16.04-lowlatency", kflavor="lowlatency"
        )
        mapping = set_resource(image_spec=image, resource=resource)
        metadata = mapping.dump_json()

        # Lack of consistency across maas in naming arch vs architecture
        # and subarch vs subarchitecture means I can't just do a simple
        # dict parameter expansion here.
        params = {
            "osystem": image.os,
            "architecture": image.arch,
            "subarchitecture": image.subarch,
            "release": image.release,
            "label": image.label,
        }
        extracted_data = extract_metadata(metadata, params)

        # We only expect the supported_subarches key from the resource data.
        expected = dict(supported_subarches=resource["subarches"])
        self.assertEqual(expected, extracted_data)

    def _make_path(self):
        osystem = factory.make_name("os")
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        release = factory.make_name("release")
        label = factory.make_name("label")
        path = (osystem, arch, subarch, release, label)
        return path, osystem, arch, subarch, release, label

    def _patch_osystem_registry(self, values, xinstall_params=None):
        get_item = self.patch(OperatingSystemRegistry, "get_item")
        item_mock = Mock()
        item_mock.get_boot_image_purposes.return_value = values
        if xinstall_params is not None:
            item_mock.get_xinstall_parameters.return_value = xinstall_params
        get_item.return_value = item_mock

    def test_extract_image_params_with_no_metadata(self):
        path, osystem, arch, subarch, release, label = self._make_path()

        # Patch OperatingSystemRegistry to return a fixed list of
        # values.
        purpose1 = factory.make_name("purpose")
        purpose2 = factory.make_name("purpose")
        xi_purpose = "xinstall"
        xi_path = factory.make_name("xi_path")
        xi_type = factory.make_name("xi_type")
        purposes = [purpose1, purpose2, xi_purpose]
        self._patch_osystem_registry(
            purposes, xinstall_params=(xi_path, xi_type)
        )

        params = extract_image_params(path, "")

        self.assertCountEqual(
            [
                {
                    "osystem": osystem,
                    "architecture": arch,
                    "subarchitecture": subarch,
                    "release": release,
                    "label": label,
                    "purpose": purpose1,
                    "xinstall_path": "",
                    "xinstall_type": "",
                },
                {
                    "osystem": osystem,
                    "architecture": arch,
                    "subarchitecture": subarch,
                    "release": release,
                    "label": label,
                    "purpose": purpose2,
                    "xinstall_path": "",
                    "xinstall_type": "",
                },
                {
                    "osystem": osystem,
                    "architecture": arch,
                    "subarchitecture": subarch,
                    "release": release,
                    "label": label,
                    "purpose": xi_purpose,
                    "xinstall_path": xi_path,
                    "xinstall_type": xi_type,
                },
            ],
            params,
        )

    def test_extract_image_params_with_metadata(self):
        path, osystem, arch, subarch, release, label = self._make_path()

        # Patch OperatingSystemRegistry to return a fixed list of
        # values.
        purpose1 = factory.make_name("purpose")
        purpose2 = factory.make_name("purpose")
        xi_purpose = "xinstall"
        xi_path = factory.make_name("xi_path")
        xi_type = factory.make_name("xi_type")
        purposes = [purpose1, purpose2, xi_purpose]
        self._patch_osystem_registry(
            purposes, xinstall_params=(xi_path, xi_type)
        )

        # Create some maas.meta content.
        image = ImageSpec(
            os=osystem,
            arch=arch,
            subarch=subarch,
            kflavor="generic",
            release=release,
            label=label,
        )
        image_resource = dict(subarches=factory.make_name("subarches"))
        mapping = BootImageMapping()
        mapping.setdefault(image, image_resource)
        maas_meta = mapping.dump_json()

        params = extract_image_params(path, maas_meta)

        self.assertCountEqual(
            [
                {
                    "osystem": osystem,
                    "architecture": arch,
                    "subarchitecture": subarch,
                    "release": release,
                    "label": label,
                    "purpose": purpose1,
                    "xinstall_path": "",
                    "xinstall_type": "",
                    "supported_subarches": image_resource["subarches"],
                },
                {
                    "osystem": osystem,
                    "architecture": arch,
                    "subarchitecture": subarch,
                    "release": release,
                    "label": label,
                    "purpose": purpose2,
                    "xinstall_path": "",
                    "xinstall_type": "",
                    "supported_subarches": image_resource["subarches"],
                },
                {
                    "osystem": osystem,
                    "architecture": arch,
                    "subarchitecture": subarch,
                    "release": release,
                    "label": label,
                    "purpose": xi_purpose,
                    "xinstall_path": xi_path,
                    "xinstall_type": xi_type,
                    "supported_subarches": image_resource["subarches"],
                },
            ],
            params,
        )
