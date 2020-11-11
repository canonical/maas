# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootResourceSet`."""


import random
from unittest import skip

from maasserver.enum import BOOT_RESOURCE_FILE_TYPE
from maasserver.models.bootresourceset import XINSTALL_TYPES
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestBootResourceSet(MAASServerTestCase):
    """Tests for the `BootResourceSet` model."""

    def make_all_boot_resource_files(self, resource_set, filetypes):
        for filetype in filetypes:
            # We set the filename to the same value as filetype, as in most
            # cases this will always be true. The simplestreams content from
            # maas.io, is formatted this way.
            factory.make_boot_resource_file_with_content(
                resource_set, filename=filetype, filetype=filetype
            )

    def test_commissionable_returns_true_when_all_filetypes_present(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        commissionable_set = {
            BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
            BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
            random.choice(
                [
                    BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE,
                    BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
                ]
            ),
        }
        self.make_all_boot_resource_files(resource_set, commissionable_set)
        self.assertTrue(resource_set.commissionable)

    def test_commissionable_returns_false_when_missing_filetypes(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        commissionable_set = {
            BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
            BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
        }
        self.make_all_boot_resource_files(resource_set, commissionable_set)
        self.assertFalse(resource_set.commissionable)

    def test_xinstallable_returns_true_when_filetype_present(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        filetype = random.choice(XINSTALL_TYPES)
        factory.make_boot_resource_file_with_content(
            resource_set, filename=filetype, filetype=filetype
        )
        self.assertTrue(resource_set.xinstallable)

    @skip("XXX: LaMontJones 2016-03-23 bug=1561259: Fails when root-image.gz.")
    def test_xinstallable_returns_false_when_missing_filetypes(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        filetype = random.choice(
            [
                BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
                BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
                BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE,
                BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
            ]
        )
        factory.make_boot_resource_file_with_content(
            resource_set, filename=filetype, filetype=filetype
        )
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
                resource_set, largefile, filename=filetype, filetype=filetype
            )
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
            content = factory.make_bytes(size=size)
            largefile = factory.make_LargeFile(
                content=content, size=total_sizes.pop()
            )
            factory.make_BootResourceFile(
                resource_set, largefile, filename=filetype, filetype=filetype
            )
        self.assertEqual(final_size, resource_set.size)

    def test_progress_handles_zero_division(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        filetype = BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE
        total_size = random.randint(1025, 2048)
        largefile = factory.make_LargeFile(content=b"", size=total_size)
        factory.make_BootResourceFile(
            resource_set, largefile, filename=filetype, filetype=filetype
        )
        self.assertEqual(0, resource_set.progress)

    def test_progress_increases_from_0_to_100(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        filetype = BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE
        total_size = 100
        current_size = 0
        largefile = factory.make_LargeFile(content=b"", size=total_size)
        factory.make_BootResourceFile(
            resource_set, largefile, filename=filetype, filetype=filetype
        )
        stream = largefile.content.open()
        self.addCleanup(stream.close)
        self.assertEqual(0, resource_set.progress)
        for _ in range(total_size):
            stream.write(b"a")
            largefile.size += 1
            largefile.save()
            current_size += 1
            self.assertAlmostEqual(
                100.0 * current_size / float(total_size), resource_set.progress
            )

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
            content = factory.make_bytes(size=size)
            largefile = factory.make_LargeFile(
                content=content, size=total_size
            )
            factory.make_BootResourceFile(
                resource_set, largefile, filename=filetype, filetype=filetype
            )
        progress = 100.0 * final_size / float(final_total_size)
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
                resource_set, filename=filetype, filetype=filetype
            )
        size = random.randint(512, 1024)
        total_size = random.randint(1025, 2048)
        filetype = types.pop()
        content = factory.make_bytes(size=size)
        largefile = factory.make_LargeFile(content=content, size=total_size)
        factory.make_BootResourceFile(
            resource_set, largefile, filename=filetype, filetype=filetype
        )
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
                resource_set, filename=filetype, filetype=filetype
            )
        self.assertTrue(resource_set.complete)
