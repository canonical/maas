# Copyright 2015-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from difflib import ndiff
import random
from textwrap import dedent

from testtools.content import text_content
from testtools.matchers import (
    ContainsDict,
    Equals,
    HasLength,
    IsInstance,
    MatchesDict,
)
import yaml

from maasserver.enum import (
    CACHE_MODE_TYPE,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    NODE_STATUS,
    PARTITION_TABLE_TYPE,
)
from maasserver.models import Bcache, Filesystem, RAID, VMFS, VolumeGroup
from maasserver.models.partitiontable import (
    BIOS_GRUB_PARTITION_SIZE,
    PARTITION_TABLE_EXTRA_SPACE,
    PREP_PARTITION_SIZE,
)
from maasserver.preseed_storage import compose_curtin_storage_config
from maasserver.storage_layouts import VMFS6StorageLayout
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class AssertStorageConfigMixin:
    def stripUUIDs(self, config):
        for entry in config:
            entry.pop("uuid", None)
        return config

    def assertStorageConfig(self, expected, observed, strip_uuids=False):
        self.assertIsInstance(observed, list)
        self.assertThat(observed, HasLength(1))
        observed = observed[0]
        observed = yaml.safe_load(observed)
        self.assertThat(
            observed,
            ContainsDict(
                {
                    "partitioning_commands": MatchesDict(
                        {"builtin": Equals(["curtin", "block-meta", "custom"])}
                    ),
                    "storage": MatchesDict(
                        {"version": Equals(1), "config": IsInstance(list)}
                    ),
                }
            ),
        )
        storage_observed = observed["storage"]["config"]
        storage_expected = yaml.safe_load(expected)["config"]
        if strip_uuids:
            storage_observed = self.stripUUIDs(storage_observed)
            storage_expected = self.stripUUIDs(storage_expected)
        if storage_observed != storage_expected:
            storage_observed_dump = yaml.safe_dump(
                storage_observed, default_flow_style=False
            )
            storage_expected_dump = yaml.safe_dump(
                storage_expected, default_flow_style=False
            )
            diff = ["--- expected", "+++ observed"]
            diff.extend(
                ndiff(
                    storage_expected_dump.splitlines(),
                    storage_observed_dump.splitlines(),
                )
            )
            self.addDetail("Differences", text_content("\n".join(diff)))
            self.fail("Storage configurations differ.")


class TestSpecialFilesystems(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - grub_device: true
            id: sda
            model: QEMU HARDDISK
            name: sda
            ptable: msdos
            serial: QM00001
            type: disk
            wipe: superblock
          - fstype: ramfs
            id: mnt-ramfs_mount
            path: /mnt/ramfs
            spec: ramfs
            type: mount
          - fstype: tmpfs
            id: mnt-tmpfs_mount
            path: /mnt/tmpfs
            spec: tmpfs
            options: noexec,size=1024k
            type: mount
    """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )
        factory.make_Filesystem(
            node_config=node.current_config,
            fstype="tmpfs",
            mount_options="noexec,size=1024k",
            mount_point="/mnt/tmpfs",
        )
        factory.make_Filesystem(
            node_config=node.current_config,
            fstype="ramfs",
            mount_options=None,
            mount_point="/mnt/ramfs",
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestExt4MetadataCSUM(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - grub_device: true
            id: sda
            model: QEMU HARDDISK
            name: sda
            ptable: gpt
            serial: QM00001
            type: disk
            wipe: superblock
          - device: sda
            id: sda-part1
            name: sda-part1
            number: 1
            offset: 4194304B
            size: 5897191424B
            type: partition
            uuid: f74ff260-2a5b-4a36-b1b8-37f746b946bf
            wipe: superblock
          - fstype: ext4
            id: sda-part1_format
            label: null
            type: format
            uuid: bf34f38c-02b7-4b4b-bb7c-e73521f9ead7
            volume: sda-part1
            extra_options:
              - -O
              - ^metadata_csum
          - device: sda-part1_format
            id: sda-part1_mount
            path: /
            type: mount
    """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            with_boot_disk=False, osystem="suse", distro_series="sles12.5"
        )
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=boot_disk
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=(5.5 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            uuid="bf34f38c-02b7-4b4b-bb7c-e73521f9ead7",
            node_config=node.current_config,
            fstype=FILESYSTEM_TYPE.EXT4,
            partition=root_partition,
            mount_options=None,
            mount_point="/",
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestSimpleGPTLayout(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU HARDDISK
            serial: QM00001
            grub_device: true
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            uuid: 6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398
            size: 536870912B
            device: sda
            wipe: superblock
            offset: 4194304B
            flag: boot
          - id: sda-part2
            name: sda-part2
            type: partition
            number: 2
            uuid: 0c1c1c3a-1e9d-4047-8ef6-328a03d513e5
            size: 1073741824B
            device: sda
            wipe: superblock
            flag: boot
          - id: sda-part3
            name: sda-part3
            type: partition
            number: 3
            uuid: 53f88413-0568-44cc-b7db-4378bdba7f6e
            size: 1073741824B
            device: sda
            wipe: superblock
          - id: sda-part4
            name: sda-part4
            type: partition
            number: 4
            uuid: f74ff260-2a5b-4a36-b1b8-37f746b946bf
            size: 5897191424B
            wipe: superblock
            device: sda
          - id: sda-part1_format
            type: format
            fstype: fat32
            label: efi
            uuid: bf34f38c-02b7-4b4b-bb7c-e73521f9ead7
            volume: sda-part1
          - id: sda-part2_format
            type: format
            fstype: ext4
            label: boot
            uuid: f98e5b7b-cbb1-437e-b4e5-1769f81f969f
            volume: sda-part2
          - id: sda-part3_format
            type: format
            fstype: swap
            label: swap
            uuid: 0f523f74-e657-4c5d-a11b-b50c4c6b0c73
            volume: sda-part3
          - id: sda-part4_format
            type: format
            fstype: xfs
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: sda-part4
          - id: sda-part4_mount
            type: mount
            path: /
            options: rw,relatime,errors=remount-ro,data=ordered
            device: sda-part4_format
          - id: sda-part2_mount
            type: mount
            path: /boot
            options: rw,relatime,block_validity,barrier,user_xattr,acl
            device: sda-part2_format
          - id: sda-part1_mount
            type: mount
            path: /boot/efi
            device: sda-part1_format
          - id: sda-part3_mount
            device: sda-part3_format
            options: pri=1,discard=pages
            type: mount
        """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            bios_boot_method="uefi",
            with_boot_disk=False,
        )
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=boot_disk
        )
        efi_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024**2,
            bootable=True,
        )
        boot_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="0c1c1c3a-1e9d-4047-8ef6-328a03d513e5",
            size=1 * 1024**3,
            bootable=True,
        )
        swap_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="53f88413-0568-44cc-b7db-4378bdba7f6e",
            size=(1.0 * 1024**3),
            bootable=False,
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=(5.5 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=efi_partition,
            fstype=FILESYSTEM_TYPE.FAT32,
            uuid="bf34f38c-02b7-4b4b-bb7c-e73521f9ead7",
            label="efi",
            mount_point="/boot/efi",
            mount_options=None,
        )
        factory.make_Filesystem(
            partition=boot_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="f98e5b7b-cbb1-437e-b4e5-1769f81f969f",
            label="boot",
            mount_point="/boot",
            mount_options="rw,relatime,block_validity,barrier,user_xattr,acl",
        )
        factory.make_Filesystem(
            partition=swap_partition,
            fstype=FILESYSTEM_TYPE.SWAP,
            uuid="0f523f74-e657-4c5d-a11b-b50c4c6b0c73",
            label="swap",
            mount_point="/bogus",
            mount_options="pri=1,discard=pages",
        )
        factory.make_Filesystem(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.XFS,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            label="root",
            mount_point="/",
            mount_options="rw,relatime,errors=remount-ro,data=ordered",
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestSimpleMBRLayout(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: msdos
            model: QEMU HARDDISK
            serial: QM00001
            grub_device: true
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            uuid: 6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398
            size: 536870912B
            device: sda
            wipe: superblock
            offset: 4194304B
            flag: boot
          - id: sda-part2
            name: sda-part2
            type: partition
            number: 2
            uuid: 0c1c1c3a-1e9d-4047-8ef6-328a03d513e5
            size: 1073741824B
            wipe: superblock
            device: sda
            flag: boot
          - id: sda-part3
            name: sda-part3
            type: partition
            number: 3
            uuid: f74ff260-2a5b-4a36-b1b8-37f746b946bf
            size: 2684354560B
            wipe: superblock
            device: sda
          - id: sda-part4
            type: partition
            number: 4
            device: sda
            flag: extended
            size: 4287627264B
          - id: sda-part5
            name: sda-part5
            type: partition
            number: 5
            uuid: 1b59e74f-6189-41a1-ba8e-fbf38df19820
            size: 2146435072B
            device: sda
            wipe: superblock
            flag: logical
          - id: sda-part6
            name: sda-part6
            type: partition
            number: 6
            uuid: 8c365c80-900b-40a1-a8c7-1e445878d19a
            size: 2138046464B
            device: sda
            wipe: superblock
            flag: logical
          - id: sda-part1_format
            type: format
            fstype: fat32
            label: efi
            uuid: bf34f38c-02b7-4b4b-bb7c-e73521f9ead7
            volume: sda-part1
          - id: sda-part2_format
            type: format
            fstype: ext4
            label: boot
            uuid: f98e5b7b-cbb1-437e-b4e5-1769f81f969f
            volume: sda-part2
          - id: sda-part3_format
            type: format
            fstype: ext4
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: sda-part3
          - id: sda-part5_format
            type: format
            fstype: ext4
            label: srv
            uuid: 9c1764f0-2b48-4127-b719-ec61ac7d5f4c
            volume: sda-part5
          - id: sda-part6_format
            type: format
            fstype: ext4
            label: srv-data
            uuid: bcac8449-3a45-4586-bdfb-c21e6ba47902
            volume: sda-part6
          - id: sda-part3_mount
            type: mount
            path: /
            device: sda-part3_format
          - id: sda-part2_mount
            type: mount
            path: /boot
            options: rw,relatime,block_validity,barrier,acl
            device: sda-part2_format
          - id: sda-part1_mount
            type: mount
            path: /boot/efi
            options: rw,nosuid,nodev
            device: sda-part1_format
          - id: sda-part5_mount
            type: mount
            path: /srv
            options: rw,nosuid,nodev,noexec,relatime
            device: sda-part5_format
          - id: sda-part6_mount
            type: mount
            path: /srv/data
            options: rw,nosuid,nodev,noexec,relatime
            device: sda-part6_format
        """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, with_boot_disk=False
        )
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=boot_disk
        )
        efi_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024**2,
            bootable=True,
        )
        boot_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="0c1c1c3a-1e9d-4047-8ef6-328a03d513e5",
            size=1 * 1024**3,
            bootable=True,
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=2.5 * 1024**3,
            bootable=False,
        )
        partition_five = factory.make_Partition(
            partition_table=partition_table,
            uuid="1b59e74f-6189-41a1-ba8e-fbf38df19820",
            size=2 * 1024**3,
            bootable=False,
        )
        partition_six = factory.make_Partition(
            partition_table=partition_table,
            uuid="8c365c80-900b-40a1-a8c7-1e445878d19a",
            size=(2 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=efi_partition,
            fstype=FILESYSTEM_TYPE.FAT32,
            uuid="bf34f38c-02b7-4b4b-bb7c-e73521f9ead7",
            label="efi",
            mount_point="/boot/efi",
            mount_options="rw,nosuid,nodev",
        )
        factory.make_Filesystem(
            partition=boot_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="f98e5b7b-cbb1-437e-b4e5-1769f81f969f",
            label="boot",
            mount_point="/boot",
            mount_options="rw,relatime,block_validity,barrier,acl",
        )
        factory.make_Filesystem(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            label="root",
            mount_point="/",
            mount_options=None,
        )
        factory.make_Filesystem(
            partition=partition_five,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="9c1764f0-2b48-4127-b719-ec61ac7d5f4c",
            label="srv",
            mount_point="/srv",
            mount_options="rw,nosuid,nodev,noexec,relatime",
        )
        factory.make_Filesystem(
            partition=partition_six,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="bcac8449-3a45-4586-bdfb-c21e6ba47902",
            label="srv-data",
            mount_point="/srv/data",
            mount_options="rw,nosuid,nodev,noexec,relatime",
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestSimpleWithEmptyDiskLayout(
    MAASServerTestCase, AssertStorageConfigMixin
):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: msdos
            model: QEMU HARDDISK
            serial: QM00001
            grub_device: true
          - id: sdb
            name: sdb
            type: disk
            wipe: superblock
            path: /dev/disk/by-id/wwn-0x55cd2e400009bf84
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            uuid: 6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398
            size: 8581545984B
            device: sda
            wipe: superblock
            offset: 4194304B
          - id: sda-part1_format
            type: format
            fstype: ext4
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: sda-part1
          - id: sda-part1_mount
            type: mount
            path: /
            options: rw,relatime,errors=remount-ro,data=writeback
            device: sda-part1_format
        """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, with_boot_disk=False
        )
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB
        factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sdb",
            id_path="/dev/disk/by-id/wwn-0x55cd2e400009bf84",
        )  # Free disk
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=boot_disk
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=(8 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            label="root",
            mount_point="/",
            mount_options="rw,relatime,errors=remount-ro,data=writeback",
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestMBRWithBootDiskWithoutPartitionsLayout(
    MAASServerTestCase, AssertStorageConfigMixin
):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: msdos
            model: QEMU HARDDISK
            serial: QM00001
          - id: sdb
            name: sdb
            type: disk
            wipe: superblock
            ptable: msdos
            path: /dev/disk/by-id/wwn-0x55cd2e400009bf84
            grub_device: true
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            uuid: 6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398
            size: 8581545984B
            device: sda
            wipe: superblock
            offset: 4194304B
          - id: sda-part1_format
            type: format
            fstype: ext4
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: sda-part1
          - id: sda-part1_mount
            type: mount
            path: /
            options: rw,relatime,errors=remount-ro,data=journal
            device: sda-part1_format
        """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, with_boot_disk=False
        )
        first_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sdb",
            id_path="/dev/disk/by-id/wwn-0x55cd2e400009bf84",
        )
        node.boot_disk = boot_disk
        node.save()
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=first_disk
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=(8 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            label="root",
            mount_point="/",
            mount_options="rw,relatime,errors=remount-ro,data=journal",
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestGPTWithBootDiskWithoutPartitionsLayout(
    MAASServerTestCase, AssertStorageConfigMixin
):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: msdos
            model: QEMU HARDDISK
            serial: QM00001
          - id: sdb
            name: sdb
            type: disk
            wipe: superblock
            ptable: gpt
            path: /dev/disk/by-id/wwn-0x55cd2e400009bf84
            grub_device: true
          - id: sdb-part1
            type: partition
            number: 1
            size: 1048576B
            device: sdb
            wipe: zero
            offset: 4194304B
            flag: bios_grub
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            uuid: 6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398
            size: 8581545984B
            device: sda
            wipe: superblock
            offset: 4194304B
          - id: sda-part1_format
            type: format
            fstype: ext4
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: sda-part1
          - id: sda-part1_mount
            type: mount
            path: /
            options: rw,relatime,errors=remount-ro,data=journal
            device: sda-part1_format
        """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture="amd64/generic",
            with_boot_disk=False,
        )
        first_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=2 * 1024**4,
            name="sdb",
            id_path="/dev/disk/by-id/wwn-0x55cd2e400009bf84",
        )  # 2 TiB
        node.boot_disk = boot_disk
        node.save()
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=first_disk
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=(8 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            label="root",
            mount_point="/",
            mount_options="rw,relatime,errors=remount-ro,data=journal",
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestGPTPXELargeBootDiskLayout(
    MAASServerTestCase, AssertStorageConfigMixin
):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU HARDDISK
            serial: QM00001
            grub_device: true
          - id: sda-part1
            type: partition
            number: 1
            size: 1048576B
            device: sda
            wipe: zero
            offset: 4194304B
            flag: bios_grub
          - id: sda-part2
            name: sda-part2
            type: partition
            number: 2
            uuid: 6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398
            size: 8581545984B
            device: sda
            wipe: superblock
          - id: sda-part2_format
            type: format
            fstype: ext4
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: sda-part2
          - id: sda-part2_mount
            type: mount
            path: /
            options: rw,relatime,errors=remount-ro,data=journal
            device: sda-part2_format
        """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture="amd64/generic",
            with_boot_disk=False,
        )
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=2 * 1024**4,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 2 TiB
        node.boot_disk = boot_disk
        node.save()
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=boot_disk
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=(
                (8 * 1024**3)
                - PARTITION_TABLE_EXTRA_SPACE
                - BIOS_GRUB_PARTITION_SIZE
            ),
            bootable=False,
        )
        factory.make_Filesystem(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            label="root",
            mount_point="/",
            mount_options="rw,relatime,errors=remount-ro,data=journal",
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestLVMOnlyVG(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU HARDDISK
            serial: QM00001
            grub_device: true
          - id: sdb
            name: sdb
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU HARDDISK
            serial: QM00002
          - id: vg0
            name: vg0
            type: lvm_volgroup
            uuid: 1793be1b-890a-44cb-9322-057b0d53b53c
            devices:
              - sdb
        """
    )

    def test_lvm_only_vg(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            bios_boot_method="uefi",
            with_boot_disk=False,
        )
        factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )
        disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sdb",
            model="QEMU HARDDISK",
            serial="QM00002",
        )
        factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=disk
        )
        VolumeGroup.objects.create_volume_group(
            name="vg0",
            uuid="1793be1b-890a-44cb-9322-057b0d53b53c",
            block_devices=[disk],
            partitions=[],
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestComplexDiskLayout(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU HARDDISK
            serial: QM00001
            grub_device: true
          - id: sdb
            name: sdb
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU SSD
            serial: QM00002
          - id: sdc
            name: sdc
            type: disk
            wipe: superblock
            model: QEMU HARDDISK
            serial: QM00003
          - id: sdd
            name: sdd
            type: disk
            wipe: superblock
            model: QEMU HARDDISK
            serial: QM00004
          - id: sde
            name: sde
            type: disk
            wipe: superblock
            model: QEMU HARDDISK
            serial: QM00005
          - id: sdf
            name: sdf
            type: disk
            wipe: superblock
            model: QEMU HARDDISK
            serial: QM00006
          - id: sdg
            name: sdg
            type: disk
            wipe: superblock
            model: QEMU HARDDISK
            serial: QM00007
          - id: md0
            name: md0
            type: raid
            raidlevel: 5
            devices:
              - sdc
              - sdd
              - sde
            spare_devices:
              - sdf
              - sdg
            ptable: gpt
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            uuid: 6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398
            size: 536870912B
            device: sda
            wipe: superblock
            offset: 4194304B
            flag: boot
          - id: sda-part2
            name: sda-part2
            type: partition
            number: 2
            uuid: 0c1c1c3a-1e9d-4047-8ef6-328a03d513e5
            size: 1073741824B
            device: sda
            wipe: superblock
            flag: boot
          - id: sda-part3
            name: sda-part3
            type: partition
            number: 3
            uuid: f74ff260-2a5b-4a36-b1b8-37f746b946bf
            size: 6970933248B
            device: sda
            wipe: superblock
          - id: sdb-part1
            name: sdb-part1
            type: partition
            number: 1
            offset: 4194304B
            uuid: f3281144-a0b6-46f1-90af-8541f97f7b1f
            size: 2139095040B
            wipe: superblock
            device: sdb
          - id: bcache0
            name: bcache0
            type: bcache
            backing_device: sda-part3
            cache_device: sdb-part1
            cache_mode: writethrough
          - id: sdb-part2
            name: sdb-part2
            type: partition
            number: 2
            uuid: ea7f96d0-b508-40d9-8495-b2163df35c9b
            size: 6442450944B
            wipe: superblock
            device: sdb
          - id: vgroot
            name: vgroot
            type: lvm_volgroup
            uuid: 1793be1b-890a-44cb-9322-057b0d53b53c
            devices:
              - sdb-part2
          - id: vgroot-lvextra
            name: lvextra
            type: lvm_partition
            volgroup: vgroot
            size: 2147483648B
          - id: vgroot-lvroot
            name: lvroot
            type: lvm_partition
            volgroup: vgroot
            size: 2147483648B
          - id: md0-part1
            name: md0-part1
            type: partition
            number: 1
            offset: 4194304B
            uuid: 18a6e885-3e6d-4505-8a0d-cf34df11a8b0
            size: 2199014866944B
            wipe: superblock
            device: md0
          - id: sda-part1_format
            type: format
            fstype: fat32
            label: efi
            uuid: bf34f38c-02b7-4b4b-bb7c-e73521f9ead7
            volume: sda-part1
          - id: sda-part2_format
            type: format
            fstype: ext4
            label: boot
            uuid: f98e5b7b-cbb1-437e-b4e5-1769f81f969f
            volume: sda-part2
          - id: vgroot-lvroot_format
            type: format
            fstype: ext4
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: vgroot-lvroot
          - id: md0-part1_format
            type: format
            fstype: ext4
            label: data
            uuid: a8ad29a3-6083-45af-af8b-06ead59f108b
            volume: md0-part1
          - id: vgroot-lvroot_mount
            type: mount
            path: /
            options: rw,relatime,errors=remount-ro,data=random
            device: vgroot-lvroot_format
          - id: sda-part2_mount
            type: mount
            path: /boot
            options: rw,relatime,block_invalidity,barrier,user_xattr,acl
            device: sda-part2_format
          - id: sda-part1_mount
            type: mount
            path: /boot/efi
            options: rw,relatime,pids
            device: sda-part1_format
          - id: md0-part1_mount
            type: mount
            path: /srv/data
            device: md0-part1_format
        """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            bios_boot_method="uefi",
            with_boot_disk=False,
        )
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB
        ssd_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sdb",
            model="QEMU SSD",
            serial="QM00002",
        )  # 8 GiB
        raid_5_disk_1 = factory.make_PhysicalBlockDevice(
            node=node,
            size=1 * 1024**4,
            name="sdc",
            model="QEMU HARDDISK",
            serial="QM00003",
        )  # 1 TiB
        raid_5_disk_2 = factory.make_PhysicalBlockDevice(
            node=node,
            size=1 * 1024**4,
            name="sdd",
            model="QEMU HARDDISK",
            serial="QM00004",
        )  # 1 TiB
        raid_5_disk_3 = factory.make_PhysicalBlockDevice(
            node=node,
            size=1 * 1024**4,
            name="sde",
            model="QEMU HARDDISK",
            serial="QM00005",
        )  # 1 TiB
        raid_5_disk_4 = factory.make_PhysicalBlockDevice(
            node=node,
            size=1 * 1024**4,
            name="sdf",
            model="QEMU HARDDISK",
            serial="QM00006",
        )  # 1 TiB
        raid_5_disk_5 = factory.make_PhysicalBlockDevice(
            node=node,
            size=1 * 1024**4,
            name="sdg",
            model="QEMU HARDDISK",
            serial="QM00007",
        )  # 1 TiB
        boot_partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=boot_disk
        )
        efi_partition = factory.make_Partition(
            partition_table=boot_partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024**2,
            bootable=True,
        )
        boot_partition = factory.make_Partition(
            partition_table=boot_partition_table,
            uuid="0c1c1c3a-1e9d-4047-8ef6-328a03d513e5",
            size=1 * 1024**3,
            bootable=True,
        )
        root_partition = factory.make_Partition(
            partition_table=boot_partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=(6.5 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=efi_partition,
            fstype=FILESYSTEM_TYPE.FAT32,
            uuid="bf34f38c-02b7-4b4b-bb7c-e73521f9ead7",
            label="efi",
            mount_point="/boot/efi",
            mount_options="rw,relatime,pids",
        )
        factory.make_Filesystem(
            partition=boot_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="f98e5b7b-cbb1-437e-b4e5-1769f81f969f",
            label="boot",
            mount_point="/boot",
            mount_options=(
                "rw,relatime,block_invalidity,barrier,user_xattr,acl"
            ),
        )
        ssd_partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=ssd_disk
        )
        cache_partition = factory.make_Partition(
            partition_table=ssd_partition_table,
            uuid="f3281144-a0b6-46f1-90af-8541f97f7b1f",
            size=(2 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        cache_set = factory.make_CacheSet(partition=cache_partition)
        Bcache.objects.create_bcache(
            name="bcache0",
            uuid="9e7bdc2d-1567-4e1c-a89a-4e20df099458",
            backing_partition=root_partition,
            cache_set=cache_set,
            cache_mode=CACHE_MODE_TYPE.WRITETHROUGH,
        )
        lvm_partition = factory.make_Partition(
            partition_table=ssd_partition_table,
            uuid="ea7f96d0-b508-40d9-8495-b2163df35c9b",
            size=(6 * 1024**3),
            bootable=False,
        )
        vgroot = VolumeGroup.objects.create_volume_group(
            name="vgroot",
            uuid="1793be1b-890a-44cb-9322-057b0d53b53c",
            block_devices=[],
            partitions=[lvm_partition],
        )
        lvroot = vgroot.create_logical_volume(
            name="lvroot",
            uuid="98fac182-45a4-4afc-ba57-a1ace0396679",
            size=2 * 1024**3,
        )
        vgroot.create_logical_volume(
            name="lvextra",
            uuid="0d960ec6-e6d0-466f-8f83-ee9c11e5b9ba",
            size=2 * 1024**3,
        )
        factory.make_Filesystem(
            block_device=lvroot,
            fstype=FILESYSTEM_TYPE.EXT4,
            label="root",
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            mount_point="/",
            mount_options="rw,relatime,errors=remount-ro,data=random",
        )
        raid_5 = RAID.objects.create_raid(
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            name="md0",
            uuid="ec7816a7-129e-471e-9735-4e27c36fa10b",
            block_devices=[raid_5_disk_1, raid_5_disk_2, raid_5_disk_3],
            spare_devices=[raid_5_disk_4, raid_5_disk_5],
        )
        raid_5_partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT,
            block_device=raid_5.virtual_device,
        )
        raid_5_partition = factory.make_Partition(
            partition_table=raid_5_partition_table,
            uuid="18a6e885-3e6d-4505-8a0d-cf34df11a8b0",
            size=(2 * 1024**4) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=raid_5_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="a8ad29a3-6083-45af-af8b-06ead59f108b",
            label="data",
            mount_point="/srv/data",
            mount_options=None,
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestSimplePower8Layout(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU HARDDISK
            serial: QM00001
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            offset: 4194304B
            size: 8388608B
            device: sda
            wipe: zero
            flag: prep
            grub_device: True
          - id: sda-part2
            name: sda-part2
            type: partition
            number: 2
            uuid: f74ff260-2a5b-4a36-b1b8-37f746b946bf
            size: 8573157376B
            wipe: superblock
            device: sda
          - id: sda-part2_format
            type: format
            fstype: ext4
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: sda-part2
          - id: sda-part2_mount
            type: mount
            path: /
            device: sda-part2_format
        """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture="ppc64el/generic",
            bios_boot_method="uefi",
            with_boot_disk=False,
        )
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=boot_disk
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=(
                (8 * 1024**3)
                - PARTITION_TABLE_EXTRA_SPACE
                - PREP_PARTITION_SIZE
            ),
            bootable=False,
        )
        factory.make_Filesystem(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            label="root",
            mount_point="/",
            mount_options=None,
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestPower8ExtraSpaceLayout(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU HARDDISK
            serial: QM00001
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            offset: 4194304B
            size: 8388608B
            device: sda
            wipe: zero
            flag: prep
            grub_device: True
          - id: sda-part2
            name: sda-part2
            type: partition
            number: 2
            uuid: f74ff260-2a5b-4a36-b1b8-37f746b946bf
            size: 7507804160B
            wipe: superblock
            device: sda
          - id: sda-part2_format
            type: format
            fstype: ext4
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: sda-part2
          - id: sda-part2_mount
            type: mount
            path: /
            device: sda-part2_format
        """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture="ppc64el/generic",
            bios_boot_method="uefi",
            with_boot_disk=False,
        )
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=boot_disk
        )
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=(7 * 1024**3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            label="root",
            mount_point="/",
            mount_options=None,
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestPower8NoPartitionTableLayout(
    MAASServerTestCase, AssertStorageConfigMixin
):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            name: sda
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU HARDDISK
            serial: QM00001
          - id: sdb
            name: sdb
            type: disk
            wipe: superblock
            ptable: gpt
            model: QEMU HARDDISK
            serial: QM00002
          - id: sdb-part1
            name: sdb-part1
            type: partition
            number: 1
            offset: 4194304B
            size: 8388608B
            device: sdb
            wipe: zero
            flag: prep
            grub_device: True
          - id: sda-part1
            name: sda-part1
            type: partition
            number: 1
            uuid: f74ff260-2a5b-4a36-b1b8-37f746b946bf
            offset: 4194304B
            size: 8573157376B
            wipe: superblock
            device: sda
          - id: sda-part1_format
            type: format
            fstype: ext4
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: sda-part1
          - id: sda-part1_mount
            type: mount
            path: /
            device: sda-part1_format
        """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture="ppc64el/generic",
            bios_boot_method="uefi",
            with_boot_disk=False,
        )
        root_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=root_disk
        )
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sdb",
            model="QEMU HARDDISK",
            serial="QM00002",
        )  # 8 GiB
        node.boot_disk = boot_disk
        node.save()
        # replace the cached object since the node is updated earlier
        node.current_config.node = node
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=(
                (8 * 1024**3)
                - PARTITION_TABLE_EXTRA_SPACE
                - PREP_PARTITION_SIZE
            ),
            bootable=False,
        )
        factory.make_Filesystem(
            partition=root_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1",
            label="root",
            mount_point="/",
            mount_options=None,
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


def shuffled(things):
    things = list(things)
    random.shuffle(things)
    return things


class TestMountOrdering(MAASServerTestCase):
    def test_mounts_are_sorted_lexically_by_path(self):
        node = factory.make_Node(status=NODE_STATUS.READY, with_boot_disk=True)
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=8 * 1024**3,
            name="sda",
            model="QEMU HARDDISK",
            serial="QM00001",
        )  # 8 GiB
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=boot_disk
        )
        # Expected mount points, in expected final (lexical) order.
        mount_points = [
            "/a",
            "/a/a",
            "/a/a/a",
            "/a/a/b",
            "/a/b",
            "/b",
            "/b/a",
            "/b/a/a",
            "/b/a/b",
            "/b/b",
        ]
        # Create enough partitions for all the mount points.
        partitions = [
            factory.make_Partition(partition_table=partition_table)
            for _ in mount_points
        ]
        # Create filesystems on each partition for each mount point, but
        # shuffle the lists of partitions and mount points to eliminate
        # implicit ordering.
        filesystems = [  # noqa
            factory.make_Filesystem(
                partition=partition, mount_point=mount_point
            )
            for mount_point, partition in zip(
                shuffled(mount_points), shuffled(partitions)
            )
        ]
        node._create_acquired_filesystems()
        [config] = compose_curtin_storage_config(node)
        devices = yaml.safe_load(config)["storage"]["config"]
        mounts = [element for element in devices if element["type"] == "mount"]
        self.assertEqual(
            ["/"] + mount_points, [mount["path"] for mount in mounts]
        )


class TestBootableRaidLayoutMBR(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            model: vendor
            name: sda
            ptable: msdos
            serial: serial-a
            type: disk
            wipe: superblock
            grub_device: true
          - grub_device: true
            id: sdb
            model: vendor
            name: sdb
            ptable: gpt
            serial: serial-b
            type: disk
            wipe: superblock
          - device: sdb
            flag: bios_grub
            id: sdb-part1
            number: 1
            offset: 4194304B
            size: 1048576B
            type: partition
            wipe: zero
          - grub_device: true
            id: sdc
            model: vendor
            name: sdc
            ptable: gpt
            serial: serial-c
            type: disk
            wipe: superblock
          - device: sdc
            flag: bios_grub
            id: sdc-part1
            number: 1
            offset: 4194304B
            size: 1048576B
            type: partition
            wipe: zero
          - device: sda
            flag: boot
            id: sda-part1
            name: sda-part1
            number: 1
            size: 1099503239168B
            type: partition
            uuid: uuid-a
            wipe: superblock
          - device: sdb
            flag: boot
            id: sdb-part2
            name: sdb-part2
            number: 2
            size: 1099503239168B
            type: partition
            uuid: uuid-b
            wipe: superblock
          - device: sdc
            flag: boot
            id: sdc-part2
            name: sdc-part2
            number: 2
            size: 1099503239168B
            type: partition
            uuid: uuid-c
            wipe: superblock
          - devices:
            - sda-part1
            - sdb-part2
            - sdc-part2
            id: md0
            name: md0
            raidlevel: 1
            spare_devices: []
            type: raid
          - fstype: ext4
            id: md0_format
            label: null
            type: format
            uuid: root-part
            volume: md0
          - device: md0_format
            id: md0_mount
            path: /
            type: mount
    """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture="amd64/generic",
            with_boot_disk=False,
        )
        terabyte = 1 * 1024**4
        partitions = []
        for letter in "abc":
            disk = factory.make_PhysicalBlockDevice(
                node=node,
                model="vendor",
                serial="serial-" + letter,
                size=terabyte,
                name="sd" + letter,
            )
            table_type = (
                PARTITION_TABLE_TYPE.MBR
                if letter == "a"
                else PARTITION_TABLE_TYPE.GPT
            )
            part_table = factory.make_PartitionTable(
                table_type=table_type, block_device=disk
            )
            partitions.append(
                factory.make_Partition(
                    partition_table=part_table,
                    uuid="uuid-" + letter,
                    size=terabyte - PARTITION_TABLE_EXTRA_SPACE,
                    bootable=True,
                )
            )
        raid = RAID.objects.create_raid(
            level=FILESYSTEM_GROUP_TYPE.RAID_1,
            name="md0",
            uuid="uuid-raid",
            partitions=partitions,
        )
        factory.make_Filesystem(
            block_device=raid.virtual_device,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="root-part",
            mount_point="/",
            mount_options=None,
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestBootableRaidLayoutUEFI(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            model: vendor
            name: sda
            ptable: gpt
            serial: serial-a
            type: disk
            wipe: superblock
            grub_device: true
          - grub_device: true
            id: sdb
            model: vendor
            name: sdb
            ptable: gpt
            serial: serial-b
            type: disk
            wipe: superblock
          - grub_device: true
            id: sdc
            model: vendor
            name: sdc
            ptable: gpt
            serial: serial-c
            type: disk
            wipe: superblock
          - device: sda
            flag: boot
            id: sda-part1
            name: sda-part1
            number: 1
            offset: 4194304B
            size: 5497549750272B
            type: partition
            uuid: uuid-a
            wipe: superblock
          - device: sdb
            flag: boot
            id: sdb-part1
            name: sdb-part1
            number: 1
            offset: 4194304B
            size: 5497549750272B
            type: partition
            uuid: uuid-b
            wipe: superblock
          - device: sdc
            flag: boot
            id: sdc-part1
            name: sdc-part1
            number: 1
            offset: 4194304B
            size: 5497549750272B
            type: partition
            uuid: uuid-c
            wipe: superblock
          - devices:
            - sda-part1
            - sdb-part1
            - sdc-part1
            id: md0
            name: md0
            raidlevel: 1
            spare_devices: []
            type: raid
          - fstype: ext4
            id: md0_format
            label: null
            type: format
            uuid: root-part
            volume: md0
          - device: md0_format
            id: md0_mount
            path: /
            type: mount
    """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture="amd64/generic",
            bios_boot_method="uefi",
            with_boot_disk=False,
        )
        size = 5 * 1024**4  # 5Tb
        partitions = []
        for letter in "abc":
            disk = factory.make_PhysicalBlockDevice(
                node=node,
                model="vendor",
                serial="serial-" + letter,
                size=size,
                name="sd" + letter,
            )
            table_type = PARTITION_TABLE_TYPE.GPT
            part_table = factory.make_PartitionTable(
                table_type=table_type, block_device=disk
            )
            partitions.append(
                factory.make_Partition(
                    partition_table=part_table,
                    uuid="uuid-" + letter,
                    size=size - PARTITION_TABLE_EXTRA_SPACE,
                    bootable=True,
                )
            )
        raid = RAID.objects.create_raid(
            level=FILESYSTEM_GROUP_TYPE.RAID_1,
            name="md0",
            uuid="uuid-raid",
            partitions=partitions,
        )
        factory.make_Filesystem(
            block_device=raid.virtual_device,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="root-part",
            mount_point="/",
            mount_options=None,
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestBootableRaidLayoutGPT(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            model: vendor
            name: sda
            ptable: gpt
            serial: serial-a
            type: disk
            wipe: superblock
            grub_device: true
          - device: sda
            flag: bios_grub
            id: sda-part1
            number: 1
            offset: 4194304B
            size: 1048576B
            type: partition
            wipe: zero
          - grub_device: true
            id: sdb
            model: vendor
            name: sdb
            ptable: gpt
            serial: serial-b
            type: disk
            wipe: superblock
          - device: sdb
            flag: bios_grub
            id: sdb-part1
            number: 1
            offset: 4194304B
            size: 1048576B
            type: partition
            wipe: zero
          - grub_device: true
            id: sdc
            model: vendor
            name: sdc
            ptable: gpt
            serial: serial-c
            type: disk
            wipe: superblock
          - device: sdc
            flag: bios_grub
            id: sdc-part1
            number: 1
            offset: 4194304B
            size: 1048576B
            type: partition
            wipe: zero
          - device: sda
            flag: boot
            id: sda-part2
            name: sda-part2
            number: 2
            size: 5497549750272B
            type: partition
            uuid: uuid-a
            wipe: superblock
          - device: sdb
            flag: boot
            id: sdb-part2
            name: sdb-part2
            number: 2
            size: 5497549750272B
            type: partition
            uuid: uuid-b
            wipe: superblock
          - device: sdc
            flag: boot
            id: sdc-part2
            name: sdc-part2
            number: 2
            size: 5497549750272B
            type: partition
            uuid: uuid-c
            wipe: superblock
          - devices:
            - sda-part2
            - sdb-part2
            - sdc-part2
            id: md0
            name: md0
            raidlevel: 1
            spare_devices: []
            type: raid
          - fstype: ext4
            id: md0_format
            label: null
            type: format
            uuid: root-part
            volume: md0
          - device: md0_format
            id: md0_mount
            path: /
            type: mount
    """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture="amd64/generic",
            with_boot_disk=False,
        )
        size = 5 * 1024**4  # 5Tb
        partitions = []
        for letter in "abc":
            disk = factory.make_PhysicalBlockDevice(
                node=node,
                model="vendor",
                serial="serial-" + letter,
                size=size,
                name="sd" + letter,
            )
            table_type = PARTITION_TABLE_TYPE.GPT
            part_table = factory.make_PartitionTable(
                table_type=table_type, block_device=disk
            )
            partitions.append(
                factory.make_Partition(
                    partition_table=part_table,
                    uuid="uuid-" + letter,
                    size=size - PARTITION_TABLE_EXTRA_SPACE,
                    bootable=True,
                )
            )
        raid = RAID.objects.create_raid(
            level=FILESYSTEM_GROUP_TYPE.RAID_1,
            name="md0",
            uuid="uuid-raid",
            partitions=partitions,
        )
        factory.make_Filesystem(
            block_device=raid.virtual_device,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="root-part",
            mount_point="/",
            mount_options=None,
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestBootableRaidLayoutGPTWithPartition(
    MAASServerTestCase, AssertStorageConfigMixin
):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            model: vendor
            name: sda
            ptable: gpt
            serial: serial-a
            type: disk
            wipe: superblock
            grub_device: true
          - device: sda
            flag: bios_grub
            id: sda-part1
            number: 1
            offset: 4194304B
            size: 1048576B
            type: partition
            wipe: zero
          - grub_device: true
            id: sdb
            model: vendor
            name: sdb
            ptable: gpt
            serial: serial-b
            type: disk
            wipe: superblock
          - device: sdb
            flag: bios_grub
            id: sdb-part1
            number: 1
            offset: 4194304B
            size: 1048576B
            type: partition
            wipe: zero
          - grub_device: true
            id: sdc
            model: vendor
            name: sdc
            ptable: gpt
            serial: serial-c
            type: disk
            wipe: superblock
          - device: sdc
            flag: bios_grub
            id: sdc-part1
            number: 1
            offset: 4194304B
            size: 1048576B
            type: partition
            wipe: zero
          - device: sda
            flag: boot
            id: sda-part2
            name: sda-part2
            number: 2
            size: 5497549750272B
            type: partition
            uuid: uuid-a
            wipe: superblock
          - device: sdb
            flag: boot
            id: sdb-part2
            name: sdb-part2
            number: 2
            size: 5497549750272B
            type: partition
            uuid: uuid-b
            wipe: superblock
          - device: sdc
            flag: boot
            id: sdc-part2
            name: sdc-part2
            number: 2
            size: 5497549750272B
            type: partition
            uuid: uuid-c
            wipe: superblock
          - devices:
            - sda-part2
            - sdb-part2
            - sdc-part2
            id: md0
            name: md0
            ptable: gpt
            raidlevel: 1
            spare_devices: []
            type: raid
          - device: md0
            id: md0-part1
            name: md0-part1
            number: 1
            offset: 4194304B
            size: 1099511627776B
            type: partition
            uuid: uuid-raid-part
            wipe: superblock
          - fstype: ext4
            id: md0-part1_format
            label: null
            type: format
            uuid: root-part
            volume: md0-part1
          - device: md0-part1_format
            id: md0-part1_mount
            path: /
            type: mount
    """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture="amd64/generic",
            with_boot_disk=False,
        )
        size = 5 * 1024**4  # 5Tb
        partitions = []
        for letter in "abc":
            disk = factory.make_PhysicalBlockDevice(
                node=node,
                model="vendor",
                serial="serial-" + letter,
                size=size,
                name="sd" + letter,
            )
            table_type = PARTITION_TABLE_TYPE.GPT
            part_table = factory.make_PartitionTable(
                table_type=table_type, block_device=disk
            )
            partitions.append(
                factory.make_Partition(
                    partition_table=part_table,
                    uuid="uuid-" + letter,
                    size=size - PARTITION_TABLE_EXTRA_SPACE,
                    bootable=True,
                )
            )
        raid = RAID.objects.create_raid(
            level=FILESYSTEM_GROUP_TYPE.RAID_1,
            name="md0",
            uuid="uuid-raid",
            partitions=partitions,
        )
        raid_part_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT,
            block_device=raid.virtual_device,
        )
        raid_partition = factory.make_Partition(
            partition_table=raid_part_table,
            uuid="uuid-raid-part",
            size=1 * 1024**4,
            bootable=False,
        )
        factory.make_Filesystem(
            partition=raid_partition,
            fstype=FILESYSTEM_TYPE.EXT4,
            uuid="root-part",
            mount_point="/",
            mount_options=None,
        )
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestVMFS(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent(
        """\
        config:
          - id: sda
            model: vendor
            name: sda
            ptable: gpt
            serial: serial-a
            type: disk
            wipe: superblock
            grub_device: true
          - id: sdb
            model: vendor
            name: sdb
            ptable: gpt
            serial: serial-b
            type: disk
            wipe: superblock
          - id: sdc
            model: vendor
            name: sdc
            ptable: gpt
            serial: serial-c
            type: disk
            wipe: superblock
          - id: sda-part1
            name: sda-part1
            device: sda
            number: 1
            type: partition
            offset: 4194304B
            size: 3145728B
            uuid: 7f79841c-9f57-4ab7-ada2-b2774e3908a3
            wipe: superblock
            flag: boot
          - id: sda-part2
            name: sda-part2
            device: sda
            number: 2
            type: partition
            size: 4294967296B
            uuid: b1a04342-60a2-47ca-8773-32b3af24c73e
            wipe: superblock
          - id: sda-part3
            name: sda-part3
            device: sda
            number: 3
            type: partition
            size: 99451142144B
            uuid: 54e698a9-e15d-409b-9e0a-2791374f6c12
            wipe: superblock
          - id: sda-part5
            name: sda-part5
            device: sda
            number: 5
            type: partition
            size: 261095424B
            uuid: af8404ca-5d62-402c-8f11-604dc0ba30a6
            wipe: superblock
          - id: sda-part6
            name: sda-part6
            device: sda
            number: 6
            type: partition
            size: 261095424B
            uuid: 34949af8-dc2f-4f9a-b81a-f26e12499f7b
            wipe: superblock
          - id: sda-part7
            name: sda-part7
            device: sda
            number: 7
            type: partition
            size: 114294784B
            uuid: e29dd323-671e-4e8f-81fe-f1f71492f231
            wipe: superblock
          - id: sda-part8
            name: sda-part8
            device: sda
            number: 8
            type: partition
            size: 298844160B
            uuid: 817ddd58-f5af-4d9a-8896-c20c06cf0f7f
            wipe: superblock
          - id: sda-part9
            name: sda-part9
            device: sda
            number: 9
            type: partition
            size: 2684354560B
            uuid: b5a745b6-7247-4397-a9a9-d484de69e35c
            wipe: superblock
          - id: sdb-part1
            name: sdb-part1
            device: sdb
            number: 1
            type: partition
            offset: 4194304B
            size: 107365793792B
            uuid: e2565df0-8ec8-4d0e-88a6-92836fce3f58
            wipe: superblock
          - id: datastore1
            name: datastore1
            type: vmfs6
            devices:
              - sda-part3
              - sdb-part1
          - id: sdc-part1
            name: sdc-part1
            device: sdc
            number: 1
            type: partition
            offset: 4194304B
            size: 107365793792B
            uuid: c803220b-7533-4276-a9b4-bfebb68813d0
            wipe: superblock
          - id: datastore2
            name: datastore2
            type: vmfs6
            devices:
              - sdc-part1
          - id: datastore1_format
            type: format
            fstype: vmfs6
            volume: datastore1
            label: null
          - id: datastore2_format
            type: format
            fstype: vmfs6
            volume: datastore2
            label: null
          - id: datastore1_mount
            type: mount
            device: datastore1_format
            path: /vmfs/volumes/datastore1
          - id: datastore2_mount
            type: mount
            device: datastore2_format
            path: /vmfs/volumes/datastore2
    """
    )

    def test_renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED,
            architecture="amd64/generic",
            osystem="esxi",
            bios_boot_method="uefi",
            distro_series="6.7",
            with_boot_disk=False,
        )
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=100 * 1024**3,
            name="sda",
            model="vendor",
            serial="serial-a",
        )
        layout = VMFS6StorageLayout(node)
        layout.configure()
        extra_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=100 * 1024**3,
            name="sdb",
            model="vendor",
            serial="serial-b",
        )
        for vmfs_part in boot_disk.get_partitiontable().partitions.all():
            if "part3" in vmfs_part.name:
                break
        vmfs = vmfs_part.get_effective_filesystem().filesystem_group
        partition = extra_disk.create_partition()
        Filesystem.objects.create(
            node_config=node.current_config,
            fstype=FILESYSTEM_TYPE.VMFS6,
            partition=partition,
            filesystem_group=vmfs,
        )
        extra_datastore_disk = factory.make_PhysicalBlockDevice(
            node=node,
            size=100 * 1024**3,
            name="sdc",
            model="vendor",
            serial="serial-c",
        )
        extra_datastore_part = extra_datastore_disk.create_partition()
        VMFS.objects.create_vmfs(
            name="datastore2", partitions=[extra_datastore_part]
        )

        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config, True)
