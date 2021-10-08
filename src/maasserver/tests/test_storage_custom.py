from maasserver.enum import FILESYSTEM_TYPE, PARTITION_TABLE_TYPE
from maasserver.models.partition import PARTITION_ALIGNMENT_SIZE
from maasserver.storage_custom import (
    _get_size,
    apply_layout_to_machine,
    BCache,
    ConfigError,
    Disk,
    FileSystem,
    get_storage_layout,
    LogicalVolume,
    LVM,
    Partition,
    RAID,
    UnappliableLayout,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.converters import round_size_to_nearest_block
from maasserver.utils.orm import reload_object
from maastesting.testcase import MAASTestCase

MB = 1000 ** 2
GB = 1000 ** 3
TB = 1000 ** 4


def rounded_size(size):
    return round_size_to_nearest_block(size, PARTITION_ALIGNMENT_SIZE, False)


class TestGetStorageLayout(MAASTestCase):
    def test_simple(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "boot": True,
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "100M",
                            "fs": "vfat",
                            "bootable": True,
                        },
                        {
                            "name": "sda2",
                            "size": "20G",
                            "fs": "ext4",
                        },
                    ],
                },
            },
            "mounts": {
                "/": {
                    "device": "sda2",
                    "options": "noatime",
                },
                "/boot/efi": {
                    "device": "sda1",
                },
            },
        }
        sda = Disk(name="sda", ptable="gpt", boot=True)
        sda1 = Partition(name="sda1", on="sda", size=100 * MB, bootable=True)
        sda1_fs = FileSystem(
            name="sda1[fs]", on="sda1", type="vfat", mount="/boot/efi"
        )
        sda2 = Partition(name="sda2", on="sda", size=20 * GB, after="sda1")
        sda2_fs = FileSystem(
            name="sda2[fs]",
            on="sda2",
            type="ext4",
            mount="/",
            mount_options="noatime",
        )
        layout = get_storage_layout(config)
        self.assertEqual(
            layout.entries,
            {
                "sda": sda,
                "sda1": sda1,
                "sda1[fs]": sda1_fs,
                "sda2": sda2,
                "sda2[fs]": sda2_fs,
            },
        )
        self.assertEqual(
            layout.sorted_entries, [sda, sda1, sda1_fs, sda2, sda2_fs]
        )
        self.assertEqual(layout.disk_names(), {"sda"})

    def test_raid(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "100M",
                            "fs": "vfat",
                        },
                        {
                            "name": "sda2",
                            "size": "20G",
                        },
                    ],
                },
                "sdb": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sdb1",
                            "size": "100M",
                        },
                        {
                            "name": "sdb2",
                            "size": "20G",
                        },
                    ],
                },
                "raid0": {
                    "type": "raid",
                    "level": 0,
                    "members": ["sda2", "sdb2"],
                    "fs": "ext4",
                },
            },
            "mounts": {
                "/": {
                    "device": "raid0",
                    "options": "noatime",
                },
                "/boot/efi": {
                    "device": "sda1",
                },
            },
        }
        sda = Disk(name="sda", ptable="gpt")
        sda1 = Partition(name="sda1", on="sda", size=100 * MB)
        sda1_fs = FileSystem(
            name="sda1[fs]", on="sda1", type="vfat", mount="/boot/efi"
        )
        sda2 = Partition(name="sda2", on="sda", size=20 * GB, after="sda1")
        sdb = Disk(name="sdb", ptable="gpt")
        sdb1 = Partition(name="sdb1", on="sdb", size=100 * MB)
        sdb2 = Partition(name="sdb2", on="sdb", size=20 * GB, after="sdb1")
        raid = RAID(name="raid0", level=0, members=["sda2", "sdb2"])
        raid_fs = FileSystem(
            name="raid0[fs]",
            on="raid0",
            type="ext4",
            mount="/",
            mount_options="noatime",
        )
        layout = get_storage_layout(config)
        self.assertEqual(
            layout.entries,
            {
                "raid0": raid,
                "sda": sda,
                "sda1": sda1,
                "sda1[fs]": sda1_fs,
                "sda2": sda2,
                "sdb": sdb,
                "sdb1": sdb1,
                "sdb2": sdb2,
                "raid0[fs]": raid_fs,
            },
        )
        self.assertEqual(
            layout.sorted_entries,
            [sda, sda1, sda1_fs, sda2, sdb, sdb1, sdb2, raid, raid_fs],
        )
        self.assertEqual(layout.disk_names(), {"sda", "sdb"})

    def test_lvm(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "100M",
                            "fs": "vfat",
                        },
                        {
                            "name": "sda2",
                            "size": "100G",
                        },
                    ],
                },
                "sdb": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sdb1",
                            "size": "100M",
                        },
                        {
                            "name": "sdb2",
                            "size": "100G",
                        },
                    ],
                },
                "storage": {
                    "type": "lvm",
                    "members": ["sda2", "sdb2"],
                    "volumes": [
                        {
                            "name": "root",
                            "size": "10G",
                            "fs": "ext4",
                        },
                        {
                            "name": "data",
                            "size": "140G",
                            "fs": "btrfs",
                        },
                    ],
                },
            },
            "mounts": {
                "/": {
                    "device": "root",
                    "options": "noatime",
                },
                "/data": {
                    "device": "data",
                },
                "/boot/efi": {
                    "device": "sda1",
                },
            },
        }
        sda = Disk(name="sda", ptable="gpt")
        sda1 = Partition(name="sda1", on="sda", size=100 * MB)
        sda1_fs = FileSystem(
            name="sda1[fs]", on="sda1", type="vfat", mount="/boot/efi"
        )
        sda2 = Partition(name="sda2", on="sda", size=100 * GB, after="sda1")
        sdb = Disk(name="sdb", ptable="gpt")
        sdb1 = Partition(name="sdb1", on="sdb", size=100 * MB)
        sdb2 = Partition(name="sdb2", on="sdb", size=100 * GB, after="sdb1")
        lvm = LVM(name="storage", members=["sda2", "sdb2"])
        root_vol = LogicalVolume(name="root", on="storage", size=10 * GB)
        root_fs = FileSystem(
            name="root[fs]",
            on="root",
            type="ext4",
            mount="/",
            mount_options="noatime",
        )
        data_vol = LogicalVolume(name="data", on="storage", size=140 * GB)
        data_fs = FileSystem(
            name="data[fs]",
            on="data",
            type="btrfs",
            mount="/data",
        )
        layout = get_storage_layout(config)
        self.assertEqual(
            layout.entries,
            {
                "sda": sda,
                "sda1": sda1,
                "sda1[fs]": sda1_fs,
                "sda2": sda2,
                "sdb": sdb,
                "sdb1": sdb1,
                "sdb2": sdb2,
                "storage": lvm,
                "root": root_vol,
                "root[fs]": root_fs,
                "data": data_vol,
                "data[fs]": data_fs,
            },
        )
        self.assertEqual(
            layout.sorted_entries,
            [
                sda,
                sda1,
                sda1_fs,
                sda2,
                sdb,
                sdb1,
                sdb2,
                lvm,
                root_vol,
                root_fs,
                data_vol,
                data_fs,
            ],
        )
        self.assertEqual(layout.disk_names(), {"sda", "sdb"})

    def test_bcache(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "100M",
                            "fs": "vfat",
                        },
                        {
                            "name": "sda2",
                            "size": "100G",
                        },
                    ],
                },
                "fast-root": {
                    "type": "bcache",
                    "backing-device": "sda2",
                    "cache-device": "sdb",
                    "cache-mode": "writeback",
                    "fs": "ext4",
                },
            },
            "mounts": {
                "/": {
                    "device": "fast-root",
                    "options": "noatime",
                },
                "/boot/efi": {
                    "device": "sda1",
                },
            },
        }
        sda = Disk(name="sda", ptable="gpt")
        sda1 = Partition(name="sda1", on="sda", size=100 * MB)
        sda1_fs = FileSystem(
            name="sda1[fs]", on="sda1", type="vfat", mount="/boot/efi"
        )
        sda2 = Partition(name="sda2", on="sda", size=100 * GB, after="sda1")
        sdb = Disk(name="sdb")
        bcache = BCache(
            name="fast-root",
            backing_device="sda2",
            cache_device="sdb",
            cache_mode="writeback",
        )
        root_fs = FileSystem(
            name="fast-root[fs]",
            on="fast-root",
            type="ext4",
            mount="/",
            mount_options="noatime",
        )
        layout = get_storage_layout(config)
        self.assertEqual(
            layout.entries,
            {
                "sda": sda,
                "sda1": sda1,
                "sda1[fs]": sda1_fs,
                "sda2": sda2,
                "sdb": sdb,
                "fast-root": bcache,
                "fast-root[fs]": root_fs,
            },
        )
        self.assertEqual(
            layout.sorted_entries,
            [sda, sda1, sda1_fs, sda2, sdb, bcache, root_fs],
        )
        self.assertEqual(layout.disk_names(), {"sda", "sdb"})

    def test_nested(self):
        config = {
            "layout": {
                "raid0": {
                    "type": "raid",
                    "level": 5,
                    "members": ["sda", "sdb", "sdc", "sdd", "sde"],
                },
                "lvm0": {
                    "type": "lvm",
                    "members": ["raid0"],
                    "volumes": [
                        {
                            "name": "root",
                            "size": "10G",
                            "fs": "ext4",
                        },
                        {
                            "name": "storage",
                            "size": "500G",
                            "fs": "xfs",
                        },
                    ],
                },
            },
            "mounts": {
                "/": {
                    "device": "root",
                    "options": "noatime",
                },
                "/storage": {
                    "device": "storage",
                },
            },
        }
        sda = Disk(name="sda")
        sdb = Disk(name="sdb")
        sdc = Disk(name="sdc")
        sdd = Disk(name="sdd")
        sde = Disk(name="sde")
        raid = RAID(
            name="raid0", level=5, members=["sda", "sdb", "sdc", "sdd", "sde"]
        )
        lvm = LVM(name="lvm0", members=["raid0"])
        root_vol = LogicalVolume(name="root", on="lvm0", size=10 * GB)
        root_fs = FileSystem(
            name="root[fs]",
            on="root",
            type="ext4",
            mount="/",
            mount_options="noatime",
        )
        storage_vol = LogicalVolume(name="storage", on="lvm0", size=500 * GB)
        storage_fs = FileSystem(
            name="storage[fs]",
            on="storage",
            type="xfs",
            mount="/storage",
        )
        layout = get_storage_layout(config)
        self.assertEqual(
            layout.entries,
            {
                "sda": sda,
                "sdb": sdb,
                "sdc": sdc,
                "sdd": sdd,
                "sde": sde,
                "raid0": raid,
                "lvm0": lvm,
                "root": root_vol,
                "root[fs]": root_fs,
                "storage": storage_vol,
                "storage[fs]": storage_fs,
            },
        )
        self.assertEqual(
            layout.sorted_entries,
            [
                sda,
                sdb,
                sdc,
                sdd,
                sde,
                raid,
                lvm,
                root_vol,
                root_fs,
                storage_vol,
                storage_fs,
            ],
        )
        self.assertEqual(
            layout.disk_names(), {"sda", "sdb", "sdc", "sdd", "sde"}
        )

    def test_invalid_device_type(self):
        config = {
            "layout": {
                "device": {
                    "type": "unknown",
                },
            },
            "mounts": {},
        }
        err = self.assertRaises(
            ConfigError,
            get_storage_layout,
            config,
        )
        self.assertEqual(str(err), "Unsupported device type 'unknown'")

    def test_invalid_partition_table_type(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "foo",
                },
            },
            "mounts": {},
        }
        err = self.assertRaises(
            ConfigError,
            get_storage_layout,
            config,
        )
        self.assertEqual(str(err), "Unknown partition table type 'foo'")

    def test_missing_partition_table_type(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "10G",
                            "fs": "ext4",
                        },
                    ],
                },
            },
            "mounts": {},
        }
        err = self.assertRaises(
            ConfigError,
            get_storage_layout,
            config,
        )
        self.assertEqual(str(err), "Partition table not specified for 'sda'")

    def test_invalid_filesytem_type(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "100M",
                            "fs": "foo",
                        },
                    ],
                },
            },
            "mounts": {},
        }
        err = self.assertRaises(
            ConfigError,
            get_storage_layout,
            config,
        )
        self.assertEqual(str(err), "Unknown filesystem type 'foo'")

    def test_invalid_bcache_cache_type(self):
        config = {
            "layout": {
                "bcache0": {
                    "type": "bcache",
                    "backing-device": "sda",
                    "cache-device": "sdb",
                    "cache-mode": "foo",
                },
            },
            "mounts": {},
        }
        err = self.assertRaises(
            ConfigError,
            get_storage_layout,
            config,
        )
        self.assertEqual(str(err), "Unknown cache mode 'foo'")

    def test_missing_required_attributes(self):
        config = {
            "layout": {
                "lvm0": {
                    "type": "lvm",
                }
            },
            "mounts": {},
        }
        err = self.assertRaises(
            ConfigError,
            get_storage_layout,
            config,
        )
        self.assertEqual(str(err), "Missing required key 'members' for 'lvm0'")

    def test_missing_filesystem_for_mountpoint(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                },
            },
            "mounts": {
                "/": {
                    "device": "sda",
                },
            },
        }
        err = self.assertRaises(
            ConfigError,
            get_storage_layout,
            config,
        )
        self.assertEqual(str(err), "Filesystem not found for device 'sda'")

    def test_missing_layout(self):
        config = {}
        err = self.assertRaises(
            ConfigError,
            get_storage_layout,
            config,
        )
        self.assertEqual(str(err), "Section 'layout' missing in config")

    def test_missing_mounts(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                },
            },
        }
        err = self.assertRaises(
            ConfigError,
            get_storage_layout,
            config,
        )
        self.assertEqual(str(err), "Section 'mounts' missing in config")


class TestGetSize(MAASTestCase):
    def test_return_size(self):
        self.assertEqual(_get_size("500M"), 500000000)
        self.assertEqual(_get_size("20G"), 20000000000)
        self.assertEqual(_get_size("3T"), 3000000000000)

    def test_float_value(self):
        self.assertEqual(_get_size("0.2M"), 200000)
        self.assertEqual(_get_size("0.5G"), 500000000)

    def test_invalid_suffix(self):
        err = self.assertRaises(ConfigError, _get_size, "10W")
        self.assertEqual(str(err), "Invalid size '10W'")

    def test_invalid_value(self):
        err = self.assertRaises(ConfigError, _get_size, "tenG")
        self.assertEqual(str(err), "Invalid size 'tenG'")

    def test_negative_value(self):
        err = self.assertRaises(ConfigError, _get_size, "-10G")
        self.assertEqual(str(err), "Invalid negative size '-10G'")


class TestApplyLayoutToMachine(MAASServerTestCase):
    def test_missing_disk(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                },
                "sdb": {
                    "type": "disk",
                    "ptable": "gpt",
                },
            },
            "mounts": {},
        }
        layout = get_storage_layout(config)
        machine = factory.make_Node()
        factory.make_PhysicalBlockDevice(node=machine, name="sda")
        err = self.assertRaises(
            UnappliableLayout, apply_layout_to_machine, layout, machine
        )
        self.assertEqual(str(err), "Unknown machine disk(s): sdb")

    def test_simple(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "boot": True,
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "100M",
                            "fs": "vfat",
                            "bootable": True,
                        },
                        {
                            "name": "sda2",
                            "size": "20G",
                            "fs": "ext4",
                        },
                    ],
                },
            },
            "mounts": {
                "/": {
                    "device": "sda2",
                    "options": "noatime",
                },
                "/boot/efi": {
                    "device": "sda1",
                },
            },
        }
        layout = get_storage_layout(config)
        machine = factory.make_Node()
        disk = factory.make_PhysicalBlockDevice(
            node=machine, name="sda", size=40 * GB
        )
        apply_layout_to_machine(layout, machine)
        ptable = disk.partitiontable_set.first()
        self.assertEqual(ptable.table_type, PARTITION_TABLE_TYPE.GPT)
        part1, part2 = ptable.partitions.order_by("id")
        self.assertEqual(part1.size, rounded_size(100 * MB))
        self.assertTrue(part1.bootable)
        self.assertEqual(part2.size, rounded_size(20 * GB))
        self.assertFalse(part2.bootable)
        fs1 = part1.filesystem_set.first()
        fs2 = part2.filesystem_set.first()
        self.assertEqual(fs1.fstype, FILESYSTEM_TYPE.VFAT)
        self.assertEqual(fs1.mount_point, "/boot/efi")
        self.assertEqual(fs1.mount_options, "")
        self.assertEqual(fs2.fstype, FILESYSTEM_TYPE.EXT4)
        self.assertEqual(fs2.mount_point, "/")
        self.assertEqual(fs2.mount_options, "noatime")

    def test_remove_previous_config(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "boot": True,
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "100M",
                            "fs": "vfat",
                            "bootable": True,
                        },
                        {
                            "name": "sda2",
                            "size": "20G",
                            "fs": "ext4",
                        },
                    ],
                },
            },
            "mounts": {
                "/": {
                    "device": "sda2",
                },
                "/boot/efi": {
                    "device": "sda1",
                },
            },
        }
        layout = get_storage_layout(config)
        machine = factory.make_Node()
        disk = factory.make_PhysicalBlockDevice(
            node=machine, name="sda", size=40 * GB
        )
        ptable = factory.make_PartitionTable(block_device=disk)
        part1 = factory.make_Partition(partition_table=ptable, size=10 * GB)
        fs1 = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.EXT4, partition=part1
        )
        part2 = factory.make_Partition(partition_table=ptable, size=15 * GB)
        fs2 = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.XFS, partition=part2
        )

        apply_layout_to_machine(layout, machine)
        for obj in (ptable, part1, fs1, part2, fs2):
            self.assertIsNone(reload_object(obj))

    def test_set_boot_disk(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                },
                "sdb": {
                    "type": "disk",
                    "ptable": "mbr",
                    "boot": True,
                },
            },
            "mounts": {},
        }
        layout = get_storage_layout(config)
        machine = factory.make_Node()
        factory.make_PhysicalBlockDevice(node=machine, name="sda")
        sdb = factory.make_PhysicalBlockDevice(node=machine, name="sdb")
        apply_layout_to_machine(layout, machine)
        self.assertEqual(machine.boot_disk, sdb)

    def test_bcache(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "100M",
                            "fs": "vfat",
                            "bootable": True,
                        },
                        {
                            "name": "sda2",
                            "size": "500M",
                            "fs": "ext2",
                        },
                        {
                            "name": "sda3",
                            "size": "800G",
                        },
                    ],
                },
                "cached-root": {
                    "type": "bcache",
                    "backing-device": "sda3",
                    "cache-device": "sdb",
                    "fs": "ext4",
                },
            },
            "mounts": {
                "/": {
                    "device": "cached-root",
                },
                "/boot/efi": {
                    "device": "sda1",
                },
                "/boot": {
                    "device": "sda2",
                },
            },
        }
        layout = get_storage_layout(config)
        machine = factory.make_Node()
        sda = factory.make_PhysicalBlockDevice(
            node=machine, name="sda", size=2 * TB
        )
        sdb = factory.make_PhysicalBlockDevice(
            node=machine, name="sdb", size=500 * GB
        )
        apply_layout_to_machine(layout, machine)
        ptable = sda.partitiontable_set.first()
        self.assertEqual(ptable.table_type, PARTITION_TABLE_TYPE.GPT)
        part1, part2, part3 = ptable.partitions.order_by("id")
        self.assertEqual(part1.size, rounded_size(100 * MB))
        self.assertTrue(part1.bootable)
        self.assertEqual(part2.size, rounded_size(500 * MB))
        self.assertFalse(part2.bootable)
        self.assertEqual(part3.size, rounded_size(800 * GB))
        self.assertFalse(part3.bootable)
        fs3 = part3.filesystem_set.first()
        self.assertEqual(fs3.fstype, FILESYSTEM_TYPE.BCACHE_BACKING)
        cache_fs = sdb.filesystem_set.first()
        self.assertEqual(cache_fs.fstype, FILESYSTEM_TYPE.BCACHE_CACHE)
        bcache = machine.blockdevice_set.get(name="cached-root")
        root_fs = bcache.filesystem_set.first()
        self.assertEqual(root_fs.fstype, FILESYSTEM_TYPE.EXT4)
        self.assertEqual(root_fs.mount_point, "/")

    def test_bcache_same_cacheset(self):
        config = {
            "layout": {
                "bcache0": {
                    "type": "bcache",
                    "backing-device": "sdb",
                    "cache-device": "sda",
                },
                "bcache1": {
                    "type": "bcache",
                    "backing-device": "sdc",
                    "cache-device": "sda",
                },
            },
            "mounts": {},
        }
        layout = get_storage_layout(config)
        machine = factory.make_Node()
        sda = factory.make_PhysicalBlockDevice(node=machine, name="sda")
        sdb = factory.make_PhysicalBlockDevice(node=machine, name="sdb")
        sdc = factory.make_PhysicalBlockDevice(node=machine, name="sdc")
        apply_layout_to_machine(layout, machine)
        fs1 = sda.get_effective_filesystem()
        self.assertEqual(fs1.fstype, FILESYSTEM_TYPE.BCACHE_CACHE)
        fs2 = sdb.get_effective_filesystem()
        self.assertEqual(fs2.fstype, FILESYSTEM_TYPE.BCACHE_BACKING)
        fs3 = sdc.get_effective_filesystem()
        self.assertEqual(fs3.fstype, FILESYSTEM_TYPE.BCACHE_BACKING)

    def test_bcache_cache_partition(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "100M",
                            "fs": "vfat",
                            "bootable": True,
                        },
                        {
                            "name": "sda2",
                            "size": "500M",
                            "fs": "ext2",
                        },
                        {
                            "name": "sda3",
                            "size": "800G",
                        },
                    ],
                },
                "sdb": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sdb1",
                            "size": "300G",
                        },
                    ],
                },
                "bcache0": {
                    "type": "bcache",
                    "backing-device": "sda3",
                    "cache-device": "sdb1",
                    "fs": "ext4",
                },
            },
            "mounts": {
                "/": {
                    "device": "bcache0",
                },
                "/boot/efi": {
                    "device": "sda1",
                },
                "/boot": {
                    "device": "sda2",
                },
            },
        }
        layout = get_storage_layout(config)
        machine = factory.make_Node()
        sda = factory.make_PhysicalBlockDevice(
            node=machine, name="sda", size=2 * TB
        )
        sdb = factory.make_PhysicalBlockDevice(
            node=machine, name="sdb", size=500 * GB
        )
        apply_layout_to_machine(layout, machine)
        ptable1 = sda.partitiontable_set.first()
        self.assertEqual(ptable1.table_type, PARTITION_TABLE_TYPE.GPT)
        part1, part2, part3 = ptable1.partitions.order_by("id")
        self.assertEqual(part1.size, rounded_size(100 * MB))
        self.assertTrue(part1.bootable)
        self.assertEqual(part2.size, rounded_size(500 * MB))
        self.assertFalse(part2.bootable)
        self.assertEqual(part3.size, rounded_size(800 * GB))
        self.assertFalse(part3.bootable)
        fs3 = part3.filesystem_set.first()
        self.assertEqual(fs3.fstype, FILESYSTEM_TYPE.BCACHE_BACKING)

        ptable2 = sdb.partitiontable_set.first()
        self.assertEqual(ptable2.table_type, PARTITION_TABLE_TYPE.GPT)
        cache_part = ptable2.partitions.first()
        cache_fs = cache_part.filesystem_set.first()
        self.assertEqual(cache_fs.fstype, FILESYSTEM_TYPE.BCACHE_CACHE)
        bcache = machine.blockdevice_set.get(name="bcache0")
        root_fs = bcache.filesystem_set.first()
        self.assertEqual(root_fs.fstype, FILESYSTEM_TYPE.EXT4)
        self.assertEqual(root_fs.mount_point, "/")

    def test_lvm(self):
        config = {
            "layout": {
                "storage": {
                    "type": "lvm",
                    "members": ["sda", "sdb", "sdc"],
                    "volumes": [
                        {
                            "name": "data1",
                            "size": "100G",
                            "fs": "ext4",
                        },
                        {
                            "name": "data2",
                            "size": "150G",
                            "fs": "btrfs",
                        },
                    ],
                },
            },
            "mounts": {
                "/data1": {
                    "device": "data1",
                },
                "/data2": {
                    "device": "data2",
                },
            },
        }
        layout = get_storage_layout(config)
        machine = factory.make_Node()
        disks = [
            factory.make_PhysicalBlockDevice(
                node=machine,
                name=name,
                size=500 * GB,
            )
            for name in config["layout"]["storage"]["members"]
        ]
        apply_layout_to_machine(layout, machine)
        for disk in disks:
            fs = disk.filesystem_set.first()
            self.assertEqual(fs.fstype, FILESYSTEM_TYPE.LVM_PV)
        data1 = machine.blockdevice_set.get(name="data1")
        self.assertEqual(data1.size, rounded_size(100 * GB))
        fs1 = data1.filesystem_set.first()
        self.assertEqual(fs1.fstype, FILESYSTEM_TYPE.EXT4)
        data2 = machine.blockdevice_set.get(name="data2")
        self.assertEqual(data2.size, rounded_size(150 * GB))
        fs2 = data2.filesystem_set.first()
        self.assertEqual(fs2.fstype, FILESYSTEM_TYPE.BTRFS)
