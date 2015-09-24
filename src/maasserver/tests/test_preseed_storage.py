# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `maasserver.preseed_storage`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []

from textwrap import dedent

from maasserver.enum import (
    CACHE_MODE_TYPE,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    NODE_STATUS,
    PARTITION_TABLE_TYPE,
)
from maasserver.models.filesystemgroup import (
    Bcache,
    RAID,
    VolumeGroup,
)
from maasserver.models.partitiontable import PARTITION_TABLE_EXTRA_SPACE
from maasserver.preseed_storage import compose_curtin_storage_config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import (
    ContainsDict,
    Equals,
    IsInstance,
    MatchesDict,
    MatchesListwise,
)
import yaml


class AssertStorageConfigMixin:

    def assertStorageConfig(self, expected, output):
        output = output[0]
        output = yaml.load(output)
        self.assertThat(output, ContainsDict({
            "partitioning_commands": MatchesDict({
                "builtin": Equals(["curtin", "block-meta", "custom"]),
            }),
            "storage": MatchesDict({
                "version": Equals(1),
                "config": IsInstance(list),
            }),
        }))
        expected = yaml.load(expected)
        output_storage = output["storage"]["config"]
        expected_storage = expected["config"]
        expected_equals = map(Equals, expected_storage)
        self.assertThat(output_storage, MatchesListwise(expected_equals))


class TestSimpleGPTLayout(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent("""\
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
            offset: 2097152B
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
            size: 6976176128B
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
            fstype: ext4
            label: root
            uuid: 90a69b22-e281-4c5b-8df9-b09514f27ba1
            volume: sda-part3
          - id: sda-part3_mount
            type: mount
            path: /
            device: sda-part3_format
          - id: sda-part2_mount
            type: mount
            path: /boot
            device: sda-part2_format
          - id: sda-part1_mount
            type: mount
            path: /boot/efi
            device: sda-part1_format
        """)

    def test__renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, bios_boot_method="uefi")
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=8 * 1024 ** 3, name="sda",
            model="QEMU HARDDISK", serial="QM00001")  # 8 GiB
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=boot_disk)
        efi_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024 ** 2,
            bootable=True)
        boot_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="0c1c1c3a-1e9d-4047-8ef6-328a03d513e5",
            size=1 * 1024 ** 3,
            bootable=True)
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=(6.5 * 1024 ** 3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False)
        factory.make_Filesystem(
            partition=efi_partition, fstype=FILESYSTEM_TYPE.FAT32,
            uuid="bf34f38c-02b7-4b4b-bb7c-e73521f9ead7", label="efi",
            mount_point="/boot/efi")
        factory.make_Filesystem(
            partition=boot_partition, fstype=FILESYSTEM_TYPE.EXT4,
            uuid="f98e5b7b-cbb1-437e-b4e5-1769f81f969f", label="boot",
            mount_point="/boot")
        factory.make_Filesystem(
            partition=root_partition, fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1", label="root",
            mount_point="/")
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestSimpleMBRLayout(MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent("""\
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
            offset: 2097152B
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
          - id: sda-part5
            name: sda-part5
            type: partition
            number: 5
            uuid: 1b59e74f-6189-41a1-ba8e-fbf38df19820
            size: 2147483648B
            device: sda
            wipe: superblock
            flag: logical
          - id: sda-part6
            name: sda-part6
            type: partition
            number: 6
            uuid: 8c365c80-900b-40a1-a8c7-1e445878d19a
            size: 2144337920B
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
          - id: sda-part5_mount
            type: mount
            path: /srv
            device: sda-part5_format
          - id: sda-part2_mount
            type: mount
            path: /boot
            device: sda-part2_format
          - id: sda-part1_mount
            type: mount
            path: /boot/efi
            device: sda-part1_format
          - id: sda-part6_mount
            type: mount
            path: /srv/data
            device: sda-part6_format
        """)

    def test__renders_expected_output(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=8 * 1024 ** 3, name="sda",
            model="QEMU HARDDISK", serial="QM00001")  # 8 GiB
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=boot_disk)
        efi_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024 ** 2,
            bootable=True)
        boot_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="0c1c1c3a-1e9d-4047-8ef6-328a03d513e5",
            size=1 * 1024 ** 3,
            bootable=True)
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=2.5 * 1024 ** 3,
            bootable=False)
        partition_five = factory.make_Partition(
            partition_table=partition_table,
            uuid="1b59e74f-6189-41a1-ba8e-fbf38df19820",
            size=2 * 1024 ** 3,
            bootable=False)
        partition_six = factory.make_Partition(
            partition_table=partition_table,
            uuid="8c365c80-900b-40a1-a8c7-1e445878d19a",
            size=(2 * 1024 ** 3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False)
        factory.make_Filesystem(
            partition=efi_partition, fstype=FILESYSTEM_TYPE.FAT32,
            uuid="bf34f38c-02b7-4b4b-bb7c-e73521f9ead7", label="efi",
            mount_point="/boot/efi")
        factory.make_Filesystem(
            partition=boot_partition, fstype=FILESYSTEM_TYPE.EXT4,
            uuid="f98e5b7b-cbb1-437e-b4e5-1769f81f969f", label="boot",
            mount_point="/boot")
        factory.make_Filesystem(
            partition=root_partition, fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1", label="root",
            mount_point="/")
        factory.make_Filesystem(
            partition=partition_five, fstype=FILESYSTEM_TYPE.EXT4,
            uuid="9c1764f0-2b48-4127-b719-ec61ac7d5f4c", label="srv",
            mount_point="/srv")
        factory.make_Filesystem(
            partition=partition_six, fstype=FILESYSTEM_TYPE.EXT4,
            uuid="bcac8449-3a45-4586-bdfb-c21e6ba47902", label="srv-data",
            mount_point="/srv/data")
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestSimpleWithEmptyDiskLayout(
        MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent("""\
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
            size: 8586788864B
            device: sda
            wipe: superblock
            offset: 2097152B
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
        """)

    def test__renders_expected_output(self):
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED)
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=8 * 1024 ** 3, name="sda",
            model="QEMU HARDDISK", serial="QM00001")  # 8 GiB
        factory.make_PhysicalBlockDevice(
            node=node, size=8 * 1024 ** 3, name="sdb",
            id_path="/dev/disk/by-id/wwn-0x55cd2e400009bf84")  # Free disk
        partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.MBR, block_device=boot_disk)
        root_partition = factory.make_Partition(
            partition_table=partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=(8 * 1024 ** 3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False)
        factory.make_Filesystem(
            partition=root_partition, fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1", label="root",
            mount_point="/")
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)


class TestComplexDiskLayout(
        MAASServerTestCase, AssertStorageConfigMixin):

    STORAGE_CONFIG = dedent("""\
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
            offset: 2097152B
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
            size: 6976176128B
            device: sda
            wipe: superblock
          - id: sdb-part1
            name: sdb-part1
            type: partition
            number: 1
            offset: 2097152B
            uuid: f3281144-a0b6-46f1-90af-8541f97f7b1f
            size: 2144337920B
            wipe: superblock
            device: sdb
          - id: bcache0
            name: bcache0
            type: bcache
            backing_device: sda-part3
            cache_device: sdb-part1
            cache_mode: writethrough
            ptable: gpt
          - id: bcache0-part1
            name: bcache0-part1
            type: partition
            number: 1
            offset: 2097152B
            uuid: 17270be2-0db6-41b5-80c9-78a20cbf968e
            size: 6973030400B
            wipe: superblock
            device: bcache0
          - id: vgroot
            name: vgroot
            type: lvm_volgroup
            uuid: 1793be1b-890a-44cb-9322-057b0d53b53c
            devices:
              - bcache0-part1
          - id: vgroot-lvextra
            name: lvextra
            type: lvm_partition
            volgroup: vgroot
            size: 3221225472B
          - id: vgroot-lvroot
            name: lvroot
            type: lvm_partition
            volgroup: vgroot
            size: 3221225472B
          - id: md0-part1
            name: md0-part1
            type: partition
            number: 1
            offset: 2097152B
            uuid: 18a6e885-3e6d-4505-8a0d-cf34df11a8b0
            size: 2199020109824B
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
            device: vgroot-lvroot_format
          - id: sda-part2_mount
            type: mount
            path: /boot
            device: sda-part2_format
          - id: sda-part1_mount
            type: mount
            path: /boot/efi
            device: sda-part1_format
          - id: md0-part1_mount
            type: mount
            path: /srv/data
            device: md0-part1_format
        """)

    def test__renders_expected_output(self):
        node = factory.make_Node(
            status=NODE_STATUS.ALLOCATED, bios_boot_method="uefi")
        boot_disk = factory.make_PhysicalBlockDevice(
            node=node, size=8 * 1024 ** 3, name="sda",
            model="QEMU HARDDISK", serial="QM00001")  # 8 GiB
        ssd_disk = factory.make_PhysicalBlockDevice(
            node=node, size=2 * 1024 ** 3, name="sdb",
            model="QEMU SSD", serial="QM00002")  # 2 GiB
        raid_5_disk_1 = factory.make_PhysicalBlockDevice(
            node=node, size=1 * 1024 ** 4, name="sdc",
            model="QEMU HARDDISK", serial="QM00003")  # 1 TiB
        raid_5_disk_2 = factory.make_PhysicalBlockDevice(
            node=node, size=1 * 1024 ** 4, name="sdd",
            model="QEMU HARDDISK", serial="QM00004")  # 1 TiB
        raid_5_disk_3 = factory.make_PhysicalBlockDevice(
            node=node, size=1 * 1024 ** 4, name="sde",
            model="QEMU HARDDISK", serial="QM00005")  # 1 TiB
        raid_5_disk_4 = factory.make_PhysicalBlockDevice(
            node=node, size=1 * 1024 ** 4, name="sdf",
            model="QEMU HARDDISK", serial="QM00006")  # 1 TiB
        raid_5_disk_5 = factory.make_PhysicalBlockDevice(
            node=node, size=1 * 1024 ** 4, name="sdg",
            model="QEMU HARDDISK", serial="QM00007")  # 1 TiB
        boot_partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=boot_disk)
        efi_partition = factory.make_Partition(
            partition_table=boot_partition_table,
            uuid="6efc2c3d-bc9d-4ee5-a7ed-c6e1574d5398",
            size=512 * 1024 ** 2,
            bootable=True)
        boot_partition = factory.make_Partition(
            partition_table=boot_partition_table,
            uuid="0c1c1c3a-1e9d-4047-8ef6-328a03d513e5",
            size=1 * 1024 ** 3,
            bootable=True)
        root_partition = factory.make_Partition(
            partition_table=boot_partition_table,
            uuid="f74ff260-2a5b-4a36-b1b8-37f746b946bf",
            size=(6.5 * 1024 ** 3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False)
        factory.make_Filesystem(
            partition=efi_partition, fstype=FILESYSTEM_TYPE.FAT32,
            uuid="bf34f38c-02b7-4b4b-bb7c-e73521f9ead7", label="efi",
            mount_point="/boot/efi")
        factory.make_Filesystem(
            partition=boot_partition, fstype=FILESYSTEM_TYPE.EXT4,
            uuid="f98e5b7b-cbb1-437e-b4e5-1769f81f969f", label="boot",
            mount_point="/boot")
        cache_partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT, block_device=ssd_disk)
        cache_partition = factory.make_Partition(
            partition_table=cache_partition_table,
            uuid="f3281144-a0b6-46f1-90af-8541f97f7b1f",
            size=(2 * 1024 ** 3) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False)
        cache_set = factory.make_CacheSet(partition=cache_partition)
        bcache0 = Bcache.objects.create_bcache(
            name="bcache0", uuid="9e7bdc2d-1567-4e1c-a89a-4e20df099458",
            backing_partition=root_partition, cache_set=cache_set,
            cache_mode=CACHE_MODE_TYPE.WRITETHROUGH)
        bcache0_partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT,
            block_device=bcache0.virtual_device)
        bcache0_partition = factory.make_Partition(
            partition_table=bcache0_partition_table,
            uuid="17270be2-0db6-41b5-80c9-78a20cbf968e",
            size=bcache0_partition_table.get_size(),
            bootable=False)
        vgroot = VolumeGroup.objects.create_volume_group(
            name="vgroot", uuid="1793be1b-890a-44cb-9322-057b0d53b53c",
            block_devices=[], partitions=[bcache0_partition])
        lvroot = vgroot.create_logical_volume(
            name="lvroot", uuid="98fac182-45a4-4afc-ba57-a1ace0396679",
            size=3 * 1024 ** 3)
        vgroot.create_logical_volume(
            name="lvextra", uuid="0d960ec6-e6d0-466f-8f83-ee9c11e5b9ba",
            size=3 * 1024 ** 3)
        factory.make_Filesystem(
            block_device=lvroot, fstype=FILESYSTEM_TYPE.EXT4,
            uuid="90a69b22-e281-4c5b-8df9-b09514f27ba1", label="root",
            mount_point="/")
        raid_5 = RAID.objects.create_raid(
            level=FILESYSTEM_GROUP_TYPE.RAID_5,
            name="md0", uuid="ec7816a7-129e-471e-9735-4e27c36fa10b",
            block_devices=[raid_5_disk_1, raid_5_disk_2, raid_5_disk_3],
            spare_devices=[raid_5_disk_4, raid_5_disk_5])
        raid_5_partition_table = factory.make_PartitionTable(
            table_type=PARTITION_TABLE_TYPE.GPT,
            block_device=raid_5.virtual_device)
        raid_5_partition = factory.make_Partition(
            partition_table=raid_5_partition_table,
            uuid="18a6e885-3e6d-4505-8a0d-cf34df11a8b0",
            size=(2 * 1024 ** 4) - PARTITION_TABLE_EXTRA_SPACE,
            bootable=False)
        factory.make_Filesystem(
            partition=raid_5_partition, fstype=FILESYSTEM_TYPE.EXT4,
            uuid="a8ad29a3-6083-45af-af8b-06ead59f108b", label="data",
            mount_point="/srv/data")
        node._create_acquired_filesystems()
        config = compose_curtin_storage_config(node)
        self.assertStorageConfig(self.STORAGE_CONFIG, config)
