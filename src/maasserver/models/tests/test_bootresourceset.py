# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootResourceSet`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.enum import BOOT_RESOURCE_FILE_TYPE
from maasserver.models.bootresourceset import (
    COMMISSIONABLE_SET,
    INSTALL_SET,
    XINSTALL_TYPES,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootResourceSet(MAASServerTestCase):
    """Tests for the `BootResourceSet` model."""

    def make_all_boot_resource_files(self, resource_set, filetypes):
        for filetype in filetypes:
            # We set the filename to the same value as filetype, as in most
            # cases this will always be true. The simplestreams content from
            # maas.ubuntu.com, is formatted this way.
            factory.make_boot_resource_file_with_content(
                resource_set, filename=filetype, filetype=filetype)

    def test_commissionable_returns_true_when_all_filetypes_present(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        self.make_all_boot_resource_files(resource_set, COMMISSIONABLE_SET)
        self.assertTrue(resource_set.commissionable)

    def test_commissionable_returns_false_when_missing_filetypes(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        types = COMMISSIONABLE_SET.copy()
        types.pop()
        self.make_all_boot_resource_files(resource_set, types)
        self.assertFalse(resource_set.commissionable)

    def test_installable_returns_true_when_all_filetypes_present(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        self.make_all_boot_resource_files(resource_set, INSTALL_SET)
        self.assertTrue(resource_set.installable)

    def test_installable_returns_false_when_missing_filetypes(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        types = INSTALL_SET.copy()
        types.pop()
        self.make_all_boot_resource_files(resource_set, types)
        self.assertFalse(resource_set.installable)

    def test_xinstallable_returns_true_when_filetype_present(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        filetype = random.choice(XINSTALL_TYPES)
        factory.make_boot_resource_file_with_content(
            resource_set, filename=filetype, filetype=filetype)
        self.assertTrue(resource_set.xinstallable)

    def test_xinstallable_returns_false_when_missing_filetypes(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        filetype = random.choice(list(INSTALL_SET))
        factory.make_boot_resource_file_with_content(
            resource_set, filename=filetype, filetype=filetype)
        self.assertFalse(resource_set.xinstallable)

    def test_total_size(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        total_size = 0
        sizes = [random.randint(512, 1024) for _ in range(3)]
        types = [
            BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
            BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
            BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
            ]
        for size in sizes:
            total_size += size
            filetype = types.pop()
            largefile = factory.make_LargeFile(size=size)
            factory.make_BootResourceFile(
                resource_set, largefile, filename=filetype, filetype=filetype)
        self.assertEqual(total_size, resource_set.total_size)

    def test_size(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        final_size = 0
        sizes = [random.randint(512, 1024) for _ in range(3)]
        total_sizes = [random.randint(1025, 2048) for _ in range(3)]
        types = [
            BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
            BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
            BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
            ]
        for size in sizes:
            final_size += size
            filetype = types.pop()
            content = factory.make_string(size=size)
            largefile = factory.make_LargeFile(
                content=content, size=total_sizes.pop())
            factory.make_BootResourceFile(
                resource_set, largefile, filename=filetype, filetype=filetype)
        self.assertEqual(final_size, resource_set.size)

    def test_progress_handles_zero_division(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        filetype = BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE
        total_size = random.randint(1025, 2048)
        content = ""
        largefile = factory.make_LargeFile(
            content=content, size=total_size)
        factory.make_BootResourceFile(
            resource_set, largefile, filename=filetype, filetype=filetype)
        self.assertEqual(0, resource_set.progress)

    def test_progress_increases_from_0_to_1(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        filetype = BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE
        total_size = 100
        current_size = 0
        largefile = factory.make_LargeFile(
            content="", size=total_size)
        factory.make_BootResourceFile(
            resource_set, largefile, filename=filetype, filetype=filetype)
        stream = largefile.content.open()
        self.addCleanup(stream.close)
        self.assertEqual(0, resource_set.progress)
        for _ in range(total_size):
            stream.write(b"a")
            current_size += 1
            self.assertAlmostEqual(
                total_size / float(current_size),
                resource_set.progress)

    def test_progress_accumulates_all_files(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        final_size = 0
        final_total_size = 0
        sizes = [random.randint(512, 1024) for _ in range(3)]
        total_sizes = [random.randint(1025, 2048) for _ in range(3)]
        types = [
            BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
            BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
            BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
            ]
        for size in sizes:
            final_size += size
            total_size = total_sizes.pop()
            final_total_size += total_size
            filetype = types.pop()
            content = factory.make_string(size=size)
            largefile = factory.make_LargeFile(
                content=content, size=total_size)
            factory.make_BootResourceFile(
                resource_set, largefile, filename=filetype, filetype=filetype)
        progress = final_total_size / float(final_size)
        self.assertAlmostEqual(progress, resource_set.progress)

    def test_complete_returns_false_for_no_files(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        self.assertFalse(resource_set.complete)

    def test_complete_returns_false_for_one_incomplete_file(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        types = [
            BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
            BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
            BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
            ]
        for _ in range(2):
            filetype = types.pop()
            factory.make_boot_resource_file_with_content(
                resource_set, filename=filetype, filetype=filetype)
        size = random.randint(512, 1024)
        total_size = random.randint(1025, 2048)
        filetype = types.pop()
        content = factory.make_string(size=size)
        largefile = factory.make_LargeFile(content=content, size=total_size)
        factory.make_BootResourceFile(
            resource_set, largefile, filename=filetype, filetype=filetype)
        self.assertFalse(resource_set.complete)

    def test_complete_returns_true_for_complete_files(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        types = [
            BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
            BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
            BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
            ]
        for _ in range(3):
            filetype = types.pop()
            factory.make_boot_resource_file_with_content(
                resource_set, filename=filetype, filetype=filetype)
        self.assertTrue(resource_set.complete)
