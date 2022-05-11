from itertools import cycle
from typing import List, Optional

from maasserver.testing.commissioning import FakeCommissioningData, GB

from .defs import STORAGE_SETUPS

DISK_NAMES = ("sda", "sdb", "sdc", "sdd", "sde", "sdf")


def make_storage_setup(machines_info: List[FakeCommissioningData]):
    storage_setups = cycle(STORAGE_SETUPS)
    for info in machines_info:
        for name in DISK_NAMES:
            info.add_disk(name, size=1000 * GB)
        info.storage_extra = make_storage_config(info, next(storage_setups))


def make_storage_config(info: FakeCommissioningData, setup: str) -> dict:
    architecture = info.debian_architecture
    if setup == "basic":
        return make_storage_basic(architecture)
    elif setup == "lvm":
        return make_storage_lvm(architecture)
    elif setup == "bcache":
        return make_storage_bcache(architecture)
    elif setup.startswith("raid-"):
        level = int(setup.split("-")[1])
        return make_storage_raid(architecture, level)
    else:
        raise RuntimeError(f"Unsupported storage setup {setup}")


def make_storage_basic(architecture: str) -> dict:
    return make_base_config(architecture, DISK_NAMES[0])


def make_storage_raid(architecture: str, level: int) -> dict:
    boot_disk, *raid_disks = DISK_NAMES
    config = make_base_config(architecture, boot_disk, root_partition=False)

    spares = []
    if level == 0:
        members, spares = raid_disks, []
    else:
        members, spares = raid_disks[:4], raid_disks[4:]
    config["layout"]["md0"] = {
        "type": "raid",
        "level": level,
        "members": members,
        "spares": spares,
        "fs": "ext4",
    }
    config["mounts"]["/"] = {
        "device": "md0",
    }
    return config


def make_storage_bcache(architecture: str) -> dict:
    boot_disk, cache_disk, *backing_disks = DISK_NAMES
    config = make_base_config(architecture, boot_disk, root_partition=False)

    for n, backing_disk in enumerate(backing_disks):
        bcache = f"bcache{n}"
        config["layout"][bcache] = {
            "type": "bcache",
            "cache-device": cache_disk,
            "backing-device": backing_disk,
            "fs": "ext4",
        }
        mountpoint = "/" if n == 0 else f"/data{n}"
        config["mounts"][mountpoint] = {"device": bcache}

    return config


def make_storage_lvm(architecture: str):
    boot_disk, *lvm_disks = DISK_NAMES
    config = make_base_config(architecture, boot_disk, root_partition=False)

    config["layout"]["vg0"] = {
        "type": "lvm",
        "members": lvm_disks,
        "volumes": [
            {
                "name": "root",
                "size": "10G",
                "fs": "ext4",
            },
            {
                "name": "data1",
                "size": "1T",
                "fs": "xfs",
            },
            {
                "name": "data2",
                "size": "2T",
                "fs": "btrfs",
            },
        ],
    }
    config["mounts"]["/"] = {"device": "root"}
    config["mounts"]["/data1"] = {"device": "data1"}
    config["mounts"]["/data2"] = {"device": "data2"}
    return config


def make_boot_disk_config(disk: str):
    return {
        "layout": {
            disk: {
                "type": "disk",
                "ptable": "gpt",
                "boot": True,
                "partitions": [],
            }
        },
        "mounts": {},
    }


def make_base_config(
    architecture: str,
    disk: str,
    boot_partition: bool = True,
    root_partition: bool = True,
) -> dict:
    config = make_boot_disk_config(disk)
    maybe_make_efi_partition(architecture, config, disk)
    if boot_partition:
        make_boot_partition(config, disk)
    if root_partition:
        make_root_partition(config, disk)
    return config


def make_root_partition(config, device):
    return add_partition_config(
        config,
        device,
        {
            "size": "8G",
            "fs": "ext4",
        },
        mount_point="/",
    )


def make_boot_partition(config, disk):
    return add_partition_config(
        config,
        disk,
        {
            "size": "1G",
            "fs": "ext2",
        },
        mount_point="/boot",
    )


def maybe_make_efi_partition(architecture, config, disk):
    if architecture == "ppc64el":
        return

    return add_partition_config(
        config,
        disk,
        {
            "size": "512M",
            "fs": "fat32",
            "bootable": True,
        },
        mount_point="/boot/efi",
    )


def add_partition_config(
    config: dict,
    disk: str,
    partition_config: dict,
    mount_point: Optional[str] = None,
) -> str:
    partitions = config["layout"][disk]["partitions"]
    partition_config = partition_config.copy()
    partitions.append(partition_config)
    partition_name = f"{disk}{len(partitions)}"
    partition_config["name"] = partition_name

    if mount_point:
        config["mounts"][mount_point] = {"device": partition_name}
    return partition_name
