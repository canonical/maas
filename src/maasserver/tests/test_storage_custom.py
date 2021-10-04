from maasserver.storage_custom import (
    BCache,
    Disk,
    FileSystem,
    get_storage_layout,
    LogicalVolume,
    LVM,
    Partition,
    RAID,
)
from maastesting.testcase import MAASTestCase


class TestGetStorageLayout(MAASTestCase):
    def test_simple(self):
        config = {
            "layout": {
                "sda": {
                    "type": "disk",
                    "ptable": "gpt",
                    "partitions": [
                        {
                            "name": "sda1",
                            "size": "100M",
                            "fs": "efi",
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
        sda = Disk(name="sda", ptable="gpt")
        sda1 = Partition(name="sda1", on="sda", size="100M")
        sda1_fs = FileSystem(
            name="sda1[fs]", on="sda1", type="efi", mount="/boot/efi"
        )
        sda2 = Partition(name="sda2", on="sda", size="20G", after="sda1")
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
                            "fs": "efi",
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
        sda1 = Partition(name="sda1", on="sda", size="100M")
        sda1_fs = FileSystem(
            name="sda1[fs]", on="sda1", type="efi", mount="/boot/efi"
        )
        sda2 = Partition(name="sda2", on="sda", size="20G", after="sda1")
        sdb = Disk(name="sdb", ptable="gpt")
        sdb1 = Partition(name="sdb1", on="sdb", size="100M")
        sdb2 = Partition(name="sdb2", on="sdb", size="20G", after="sdb1")
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
                            "fs": "efi",
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
        sda1 = Partition(name="sda1", on="sda", size="100M")
        sda1_fs = FileSystem(
            name="sda1[fs]", on="sda1", type="efi", mount="/boot/efi"
        )
        sda2 = Partition(name="sda2", on="sda", size="100G", after="sda1")
        sdb = Disk(name="sdb", ptable="gpt")
        sdb1 = Partition(name="sdb1", on="sdb", size="100M")
        sdb2 = Partition(name="sdb2", on="sdb", size="100G", after="sdb1")
        lvm = LVM(name="storage", members=["sda2", "sdb2"])
        root_vol = LogicalVolume(name="root", on="storage", size="10G")
        root_fs = FileSystem(
            name="root[fs]",
            on="root",
            type="ext4",
            mount="/",
            mount_options="noatime",
        )
        data_vol = LogicalVolume(name="data", on="storage", size="140G")
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
                            "fs": "efi",
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
        sda1 = Partition(name="sda1", on="sda", size="100M")
        sda1_fs = FileSystem(
            name="sda1[fs]", on="sda1", type="efi", mount="/boot/efi"
        )
        sda2 = Partition(name="sda2", on="sda", size="100G", after="sda1")
        sdb = Disk(name="sdb")
        bcache = BCache(
            name="fast-root", backing_device="sda2", cache_device="sdb"
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
        root_vol = LogicalVolume(name="root", on="lvm0", size="10G")
        root_fs = FileSystem(
            name="root[fs]",
            on="root",
            type="ext4",
            mount="/",
            mount_options="noatime",
        )
        storage_vol = LogicalVolume(name="storage", on="lvm0", size="500G")
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
