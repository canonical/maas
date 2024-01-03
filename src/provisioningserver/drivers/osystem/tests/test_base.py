# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.osystem`."""


import os
from unittest.mock import sentinel

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers import osystem as osystem_module
from provisioningserver.drivers.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystemRegistry,
)
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.testing.os import make_osystem
from provisioningserver.utils.testing import RegistryFixture


class TestOperatingSystem(MAASTestCase):
    def make_usable_osystem(self):
        return make_osystem(
            self,
            factory.make_name("os"),
            [
                BOOT_IMAGE_PURPOSE.COMMISSIONING,
                BOOT_IMAGE_PURPOSE.INSTALL,
                BOOT_IMAGE_PURPOSE.XINSTALL,
            ],
        )

    def make_boot_image_for(self, osystem, release):
        return dict(osystem=osystem, release=release)

    def configure_list_boot_images_for(self, osystem):
        images = [
            self.make_boot_image_for(osystem.name, release)
            for release in osystem.get_supported_releases()
        ]
        self.patch_autospec(
            osystem_module, "list_boot_images_for"
        ).return_value = images
        return images

    def test_is_release_supported(self):
        osystem = self.make_usable_osystem()
        releases = [factory.make_name("release") for _ in range(3)]
        supported = [
            osystem.is_release_supported(release) for release in releases
        ]
        self.assertEqual([True, True, True], supported)

    def test_format_release_choices(self):
        osystem = self.make_usable_osystem()
        releases = osystem.get_supported_releases()
        self.assertCountEqual(
            [(release, release) for release in releases],
            osystem.format_release_choices(releases),
        )

    def test_format_release_choices_sorts(self):
        osystem = self.make_usable_osystem()
        releases = osystem.get_supported_releases()
        self.assertEqual(
            [(release, release) for release in sorted(releases, reverse=True)],
            osystem.format_release_choices(releases),
        )

    def test_gen_supported_releases(self):
        osystem = self.make_usable_osystem()
        images = self.configure_list_boot_images_for(osystem)
        releases = {image["release"] for image in images}
        self.assertCountEqual(releases, osystem.gen_supported_releases())

    def test_get_xinstall_parameters(self):
        # The base OperatingSystems class should only look for root-tgz,
        # child classes can override.
        osystem = make_osystem(self, factory.make_name("os"))
        tmpdir = self.make_dir()
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        release = factory.make_name("release")
        label = factory.make_name("label")
        dir_path = os.path.join(
            tmpdir, osystem.name, arch, subarch, release, label
        )
        os.makedirs(dir_path)
        for fname in ["squashfs", "root-tgz", "root-dd"]:
            factory.make_file(dir_path, fname)
        self.useFixture(ClusterConfigurationFixture(tftp_root=tmpdir))
        self.assertEqual(
            ("root-tgz", "tgz"),
            osystem.get_xinstall_parameters(arch, subarch, release, label),
        )


class TestFindImage(MAASTestCase):
    scenarios = [
        (
            "squashfs",
            {
                "squashfs": True,
                "tgz": True,
                "dd": True,
                "fname": "squashfs",
                "expected": ("squashfs", "squashfs"),
            },
        ),
        (
            "squashfs default",
            {
                "squashfs": True,
                "tgz": True,
                "dd": True,
                "fname": None,
                "expected": ("squashfs", "squashfs"),
            },
        ),
        (
            "root-tgz",
            {
                "squashfs": False,
                "tgz": True,
                "dd": True,
                "fname": "root-tgz",
                "expected": ("root-tgz", "tgz"),
            },
        ),
        (
            "root-tgz default",
            {
                "squashfs": False,
                "tgz": True,
                "dd": True,
                "fname": None,
                "expected": ("root-tgz", "tgz"),
            },
        ),
        (
            "root.tgz",
            {
                "squashfs": False,
                "tgz": True,
                "dd": True,
                "fname": "root.tgz",
                "expected": ("root.tgz", "tgz"),
            },
        ),
        (
            "root-tbz",
            {
                "squashfs": False,
                "tgz": True,
                "dd": True,
                "fname": "root-tbz",
                "expected": ("root-tbz", "tbz"),
            },
        ),
        (
            "root.tbz",
            {
                "squashfs": False,
                "tgz": True,
                "dd": True,
                "fname": "root.tbz",
                "expected": ("root.tbz", "tbz"),
            },
        ),
        (
            "root-txz",
            {
                "squashfs": False,
                "tgz": True,
                "dd": True,
                "fname": "root-txz",
                "expected": ("root-txz", "txz"),
            },
        ),
        (
            "root.txz",
            {
                "squashfs": False,
                "tgz": True,
                "dd": True,
                "fname": "root.txz",
                "expected": ("root.txz", "txz"),
            },
        ),
        (
            "root-dd",
            {
                "squashfs": False,
                "tgz": False,
                "dd": True,
                "fname": "root-dd",
                "expected": ("root-dd", "dd-tgz"),
            },
        ),
        (
            "root-dd.tar",
            {
                "squashfs": False,
                "tgz": False,
                "dd": True,
                "fname": "root-dd.tar",
                "expected": ("root-dd.tar", "dd-tar"),
            },
        ),
        (
            "root-dd.raw",
            {
                "squashfs": False,
                "tgz": False,
                "dd": True,
                "fname": "root-dd.raw",
                "expected": ("root-dd.raw", "dd-raw"),
            },
        ),
        (
            "root-dd.bz2",
            {
                "squashfs": False,
                "tgz": False,
                "dd": True,
                "fname": "root-dd.bz2",
                "expected": ("root-dd.bz2", "dd-bz2"),
            },
        ),
        (
            "root-dd.gz",
            {
                "squashfs": False,
                "tgz": False,
                "dd": True,
                "fname": "root-dd.gz",
                "expected": ("root-dd.gz", "dd-gz"),
            },
        ),
        (
            "root-dd.xz",
            {
                "squashfs": False,
                "tgz": False,
                "dd": True,
                "fname": "root-dd.xz",
                "expected": ("root-dd.xz", "dd-xz"),
            },
        ),
        (
            "root-dd.tar.bz2",
            {
                "squashfs": False,
                "tgz": False,
                "dd": True,
                "fname": "root-dd.tar.bz2",
                "expected": ("root-dd.tar.bz2", "dd-tbz"),
            },
        ),
        (
            "root-dd.tar.xz",
            {
                "squashfs": False,
                "tgz": False,
                "dd": True,
                "fname": "root-dd.tar.xz",
                "expected": ("root-dd.tar.xz", "dd-txz"),
            },
        ),
        (
            "root-dd default",
            {
                "squashfs": False,
                "tgz": False,
                "dd": True,
                "fname": None,
                "expected": ("root-dd", "dd-tgz"),
            },
        ),
    ]

    def test_find_image(self):
        osystem = make_osystem(self, factory.make_name("os"))
        tmpdir = self.make_dir()
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        release = factory.make_name("release")
        label = factory.make_name("label")
        dir_path = os.path.join(
            tmpdir, osystem.name, arch, subarch, release, label
        )
        os.makedirs(dir_path)
        if self.fname:
            factory.make_file(dir_path, self.fname)
        self.useFixture(ClusterConfigurationFixture(tftp_root=tmpdir))
        filesystems = osystem._get_image_filetypes(
            tgz=self.tgz,
            dd=self.dd,
            squashfs=self.squashfs,
        )
        self.assertEqual(
            self.expected,
            osystem._find_image(
                arch,
                subarch,
                release,
                label,
                filesystems,
            ),
        )


class TestOperatingSystemRegistry(MAASTestCase):
    def setUp(self):
        super().setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_operating_system_registry(self):
        self.assertEqual([], list(OperatingSystemRegistry))
        OperatingSystemRegistry.register_item("resource", sentinel.resource)
        self.assertIn(
            sentinel.resource, (item for name, item in OperatingSystemRegistry)
        )
