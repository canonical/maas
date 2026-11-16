# Copyright 2016-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasserver.enum import (
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
)
from maasserver.forms.filesystem import (
    MountFilesystemForm,
    MountNonStorageFilesystemForm,
    UnmountNonStorageFilesystemForm,
)
from maasserver.models import Filesystem
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestMountFilesystemFormWithoutSubstrate(MAASServerTestCase):
    def test_is_not_valid_if_there_is_no_filesystem(self):
        data = {"mount_point": factory.make_absolute_path()}
        form = MountFilesystemForm(None, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because block device does "
            "not have a filesystem.",
        )
        self.assertEqual(
            {
                "__all__": [
                    "Cannot mount an unformatted partition or block device."
                ]
            },
            form._errors,
        )


class TestMountFilesystemForm(MAASServerTestCase):
    scenarios = (
        (
            "partition",
            {
                "make_substrate": lambda: {
                    "partition": factory.make_Partition()
                }
            },
        ),
        (
            "block-device",
            {
                "make_substrate": lambda: {
                    "block_device": factory.make_PhysicalBlockDevice()
                }
            },
        ),
    )

    def test_requires_mount_point_when_fs_uses_mount_point(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.EXT4, **substrate
        )
        form = MountFilesystemForm(filesystem, data={})
        self.assertTrue(filesystem.uses_mount_point)
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual({"mount_point"}, form.errors.keys())

    def test_ignores_mount_point_when_fs_does_not_use_mount_point(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.SWAP, **substrate
        )
        form = MountFilesystemForm(filesystem, data={})
        self.assertFalse(filesystem.uses_mount_point)
        self.assertTrue(form.is_valid(), form.errors)

    def test_is_not_valid_if_invalid_absolute_path(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.EXT4, **substrate
        )
        data = {"mount_point": factory.make_absolute_path()[1:]}
        form = MountFilesystemForm(filesystem, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because it's not an absolute path.",
        )
        self.assertEqual(
            {"mount_point": ["Enter a valid value."]}, form._errors
        )

    def test_is_not_valid_if_absolute_path_empty(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.EXT4, **substrate
        )
        data = {"mount_point": ""}
        form = MountFilesystemForm(filesystem, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because its not an absolute path.",
        )
        self.assertEqual(
            {"mount_point": ["This field is required."]}, form._errors
        )

    def test_is_not_valid_if_invalid_absolute_path_too_long(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.EXT4, **substrate
        )
        mount_point = factory.make_absolute_path(directory_length=4096)
        data = {"mount_point": mount_point}
        form = MountFilesystemForm(filesystem, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because its not an absolute path.",
        )
        self.assertEqual(
            {
                "mount_point": [
                    "Ensure this value has at most 4095 characters "
                    "(it has %s)." % len(mount_point)
                ]
            },
            form._errors,
        )

    def test_is_not_valid_if_substrate_in_filesystem_group(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, **substrate
        )
        factory.make_FilesystemGroup(
            group_type=FILESYSTEM_GROUP_TYPE.LVM_VG, filesystems=[filesystem]
        )
        data = {"mount_point": factory.make_absolute_path()}
        form = MountFilesystemForm(filesystem, data=data)
        self.assertFalse(
            form.is_valid(),
            "Should be invalid because block device is in a filesystem group.",
        )
        self.assertEqual(
            {
                "__all__": [
                    "Filesystem is part of a filesystem group, and cannot be "
                    "mounted."
                ]
            },
            form._errors,
        )

    def test_sets_mount_point_and_options_on_filesystem(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.EXT4, **substrate
        )
        self.assertFalse(filesystem.is_mounted)
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        data = {
            "mount_point": mount_point,
            # Whitespace is stripped by form validation.
            "mount_options": "  " + mount_options + "\t\n",
        }
        form = MountFilesystemForm(filesystem, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        self.assertEqual(mount_point, filesystem.mount_point)
        self.assertEqual(mount_options, filesystem.mount_options)
        self.assertTrue(filesystem.is_mounted)

    def test_sets_mount_point_to_none_and_options_on_swap(self):
        substrate = self.make_substrate()
        filesystem = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.SWAP, **substrate
        )
        self.assertFalse(filesystem.is_mounted)
        mount_options = factory.make_name("options")
        data = {"mount_options": mount_options}
        form = MountFilesystemForm(filesystem, data=data)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        self.assertEqual("none", filesystem.mount_point)
        self.assertEqual(mount_options, filesystem.mount_options)
        self.assertTrue(filesystem.is_mounted)


class TestMountNonStorageFilesystemForm(MAASServerTestCase):
    def test_requires_fstype_and_mount_point(self):
        node = factory.make_Node()
        form = MountNonStorageFilesystemForm(node, data={})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "fstype": ["This field is required."],
                "mount_point": ["This field is required."],
            },
        )


class TestMountNonStorageFilesystemFormScenarios(MAASServerTestCase):
    scenarios = [
        (displayname, {"fstype": name, "acquired": acquired})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES
        for acquired in [False, True]
        if name not in Filesystem.TYPES_REQUIRING_STORAGE
    ]

    def test_creates_filesystem_with_mount_point_and_options(self):
        owner = None
        if self.acquired:
            owner = factory.make_User()
        node = factory.make_Node(owner=owner)
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        form = MountNonStorageFilesystemForm(
            node,
            data={
                "fstype": self.fstype,
                "mount_point": mount_point,
                # Whitespace is stripped by form validation.
                "mount_options": "  " + mount_options + "\t\n",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        filesystem = form.save()
        self.assertEqual(filesystem.node_config, node.current_config)
        self.assertEqual(filesystem.fstype, self.fstype)
        self.assertEqual(filesystem.mount_point, mount_point)
        self.assertEqual(filesystem.mount_options, mount_options)
        self.assertTrue(filesystem.is_mounted)
        self.assertEqual(filesystem.acquired, self.acquired)


class TestUnmountNonStorageFilesystemForm(MAASServerTestCase):
    def test_requires_mount_point(self):
        node = factory.make_Node()
        form = UnmountNonStorageFilesystemForm(node, data={})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"mount_point": ["This field is required."]}, form.errors
        )

    def test_will_not_unmount_filesystem_on_partition(self):
        node = factory.make_Node()
        partition = factory.make_Partition(node=node)
        filesystem = factory.make_Filesystem(
            mount_point=factory.make_absolute_path(), partition=partition
        )
        form = UnmountNonStorageFilesystemForm(
            node, data={"mount_point": filesystem.mount_point}
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "mount_point": [
                    "No special filesystem is mounted at this path."
                ]
            },
        )

    def test_will_not_unmount_filesystem_on_block_device(self):
        node = factory.make_Node()
        block_device = factory.make_BlockDevice(node=node)
        filesystem = factory.make_Filesystem(
            mount_point=factory.make_absolute_path(), block_device=block_device
        )
        form = UnmountNonStorageFilesystemForm(
            node, data={"mount_point": filesystem.mount_point}
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "mount_point": [
                    "No special filesystem is mounted at this path."
                ]
            },
        )


class TestUnmountNonStorageFilesystemFormScenarios(MAASServerTestCase):
    scenarios = [
        (displayname, {"fstype": name})
        for name, displayname in FILESYSTEM_FORMAT_TYPE_CHOICES
        if name not in Filesystem.TYPES_REQUIRING_STORAGE
    ]

    def test_unmounts_filesystem_with_mount_point(self):
        node = factory.make_Node()
        mount_point = factory.make_absolute_path()
        mount_options = factory.make_name("options")
        filesystem = factory.make_Filesystem(
            node_config=node.current_config,
            mount_point=mount_point,
            mount_options=mount_options,
        )
        form = UnmountNonStorageFilesystemForm(
            node, data={"mount_point": mount_point}
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertIsNone(reload_object(filesystem))
