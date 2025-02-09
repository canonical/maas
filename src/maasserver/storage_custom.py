# Copyright 2021-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Parse format for custom storage configuration."""

import dataclasses
from pathlib import Path
from typing import Any, cast, Dict, List, Optional, Set

import jsonschema
import yaml

from maasserver import models
from maasserver.enum import (
    CACHE_MODE_TYPE,
    FILESYSTEM_TYPE,
    FILESYSTEM_TYPE_CHOICES,
)

SCHEMA_FILE = Path(__file__).parent / "storage_custom_schema.yaml"


@dataclasses.dataclass
class StorageEntry:
    name: str

    def deps(self) -> Set[str]:
        return set()


@dataclasses.dataclass
class SpecialDevice(StorageEntry):
    pass


@dataclasses.dataclass
class Disk(StorageEntry):
    ptable: str = ""
    boot: bool = False


@dataclasses.dataclass
class FileSystem(StorageEntry):
    on: str
    type: str
    mount: str = ""
    mount_options: str = ""

    def deps(self) -> Set[str]:
        return {self.on}


@dataclasses.dataclass
class Partition(StorageEntry):
    on: str
    size: int
    bootable: bool = False
    after: str = ""

    def deps(self) -> Set[str]:
        depends = {self.on}
        if self.after:
            depends.add(self.after)
        return depends


@dataclasses.dataclass
class RAID(StorageEntry):
    level: int
    members: List[str]
    spares: List[str]

    def deps(self) -> Set[str]:
        return set(self.members + self.spares)


@dataclasses.dataclass
class LVM(StorageEntry):
    members: List[str]

    def deps(self) -> Set[str]:
        return set(self.members)


@dataclasses.dataclass
class LogicalVolume(Partition):
    pass


@dataclasses.dataclass
class BCache(StorageEntry):
    backing_device: str
    cache_device: str
    cache_mode: str = CACHE_MODE_TYPE.WRITETHROUGH

    def deps(self) -> Set[str]:
        return {self.backing_device, self.cache_device}


@dataclasses.dataclass
class StorageLayout:
    """A storage layout.

    It is described by a series of entries that must be configured in order to
    fulfill the layout.
    """

    entries: Dict[str, StorageEntry]
    sorted_entries: List[StorageEntry]

    def disk_names(self) -> Set[str]:
        """Return a list of physical disk names required by the layout."""
        return {
            entry.name
            for entry in self.sorted_entries
            if isinstance(entry, Disk)
        }


class ConfigError(Exception):
    """Provided configuration is invalid."""


class UnappliableLayout(Exception):
    """Layout can't be applied to the machine."""


Config = Dict[str, Any]


def get_storage_layout(config: Config) -> StorageLayout:
    """Return a StorageLayout for the provided configuration."""
    _validate_schema(config)
    for base_key in ("layout", "mounts"):
        if base_key not in config:
            raise ConfigError(f"Section '{base_key}' missing in config")
    entries = _get_storage_entries(config["layout"])
    entries_map = {entry.name: entry for entry in entries}
    _set_mountpoints(entries_map, config["mounts"])
    sorted_entries = _sort_entries(entries)
    return StorageLayout(entries=entries_map, sorted_entries=sorted_entries)


def apply_layout_to_machine(layout: StorageLayout, machine):
    # clear everything storage-related, except physical disks
    machine._clear_full_storage_configuration()

    block_devices = {
        disk.name: disk
        for disk in machine.current_config.blockdevice_set.all()
    }
    missing_disks = layout.disk_names() - set(
        machine.physicalblockdevice_set.values_list("name", flat=True)
    )
    if missing_disks:
        missing_disks_list = ", ".join(sorted(missing_disks))
        raise UnappliableLayout(
            f"Unknown machine disk(s): {missing_disks_list}"
        )
    for entry in layout.sorted_entries:
        entry_type = type(entry).__name__
        apply_layout = _LAYOUT_APPLIERS[entry_type]
        apply_layout(machine, entry, block_devices)


def _choices(choices_tuple):
    return tuple(choice[0] for choice in choices_tuple)


def _get_filesystem(name: str, data: Config) -> Optional[FileSystem]:
    fs = data.get("fs")
    if not fs:
        return None
    if fs not in _choices(FILESYSTEM_TYPE_CHOICES):
        raise ConfigError(f"Unknown filesystem type '{fs}'")
    return FileSystem(
        name=f"{name}[fs]",
        on=name,
        type=fs,
    )


def _validate_partition_table(name: str, data: Config) -> str:
    ptable = data.get("ptable", "")
    if not ptable and data.get("partitions"):
        raise ConfigError(f"Partition table not specified for '{name}'")
    return ptable


def _flatten_disk(name: str, data: Config) -> List[StorageEntry]:
    ptable = _validate_partition_table(name, data)
    items: List[StorageEntry] = [
        Disk(name=name, ptable=ptable, boot=data.get("boot", False))
    ]
    items.extend(_disk_partitions(name, data.get("partitions", [])))
    return items


def _flatten_raid(name: str, data: Config) -> List[StorageEntry]:
    level = data["level"]
    members = data.get("members", [])
    spares = data.get("spares", [])
    if set(members) & set(spares):
        raise ConfigError(
            f"RAID '{name}' has duplicated devices in members and spares"
        )
    if spares and level == 0:
        raise ConfigError("RAID level 0 doesn't support spares")
    items: List[StorageEntry] = [
        RAID(
            name=name,
            level=level,
            members=members,
            spares=spares,
        )
    ]
    fs = _get_filesystem(name, data)
    if fs:
        items.append(fs)
    return items


def _flatten_bcache(name: str, data: Config) -> List[StorageEntry]:
    cache_mode = data.get("cache-mode", CACHE_MODE_TYPE.WRITETHROUGH)
    items: List[StorageEntry] = [
        BCache(
            name=name,
            backing_device=data["backing-device"],
            cache_device=data["cache-device"],
            cache_mode=cache_mode,
        )
    ]
    fs = _get_filesystem(name, data)
    if fs:
        items.append(fs)
    return items


def _flatten_lvm(name: str, data: Config) -> List[StorageEntry]:
    items: List[StorageEntry] = [
        LVM(
            name=name,
            members=data["members"],
        )
    ]
    for volume in data.get("volumes", []):
        vol_name = volume["name"]
        items.append(
            LogicalVolume(
                name=vol_name,
                on=name,
                size=_get_size(volume["size"]),
            )
        )
        fs = _get_filesystem(vol_name, volume)
        if fs:
            items.append(fs)
    return items


def _flatten_special(name: str, data: Config) -> List[StorageEntry]:
    fstype = data.get("fs")
    if fstype not in (FILESYSTEM_TYPE.TMPFS, FILESYSTEM_TYPE.RAMFS):
        raise ConfigError(f"Invalid special filesystem '{fstype}'")
    items: List[StorageEntry] = [
        SpecialDevice(name=name),
        _get_filesystem(name, data),
    ]
    return items


def _disk_partitions(
    disk_name: str, partitions_data: List[Config]
) -> List[StorageEntry]:
    items: List[StorageEntry] = []
    after = ""
    for part in partitions_data:
        part_name = part["name"]
        items.append(
            Partition(
                name=part_name,
                on=disk_name,
                size=_get_size(part["size"]),
                bootable=part.get("bootable", False),
                after=after,
            )
        )
        after = part_name
        fs = _get_filesystem(part_name, part)
        if fs:
            items.append(fs)
    return items


_FLATTENERS = {
    "bcache": _flatten_bcache,
    "disk": _flatten_disk,
    "lvm": _flatten_lvm,
    "raid": _flatten_raid,
    "special": _flatten_special,
}


def _flatten(config: Config) -> List[StorageEntry]:
    items: List[StorageEntry] = []
    for name, data in config.items():
        try:
            device_type = data["type"]
            flattener = _FLATTENERS[device_type]
        except KeyError:
            raise ConfigError(f"Unsupported device type '{device_type}'")  # noqa: B904

        try:
            items.extend(flattener(name, data))
        except KeyError as e:
            key = e.args[0]
            raise ConfigError(f"Missing required key '{key}' for '{name}'")  # noqa: B904
    return items


def _apply_layout_disk(
    machine: models.Node, entry: StorageEntry, block_devices: List
):
    if not entry.ptable:
        return
    disk = block_devices[entry.name]
    if entry.boot:
        machine.boot_disk = disk.physicalblockdevice
        machine.save()
    partition_table = models.PartitionTable.objects.create(
        block_device=disk,
        table_type=entry.ptable.upper(),
    )
    # cache the partition table to avoid having to fetch it when creating
    # partitions
    disk.partition_table = partition_table


def _apply_layout_partition(
    machine: models.Node, entry: StorageEntry, block_devices: List
):
    device = block_devices[entry.on]
    # if there is a partition table for the device, it has been cached above
    partition_table = getattr(device, "partition_table", None)
    block_devices[entry.name] = models.Partition.objects.create(
        partition_table=partition_table,
        bootable=entry.bootable,
        size=entry.size,
    )


def _apply_layout_filesystem(
    machine: models.Node, entry: StorageEntry, block_devices: List
):
    params = {
        "fstype": entry.type,
        "mount_point": entry.mount or None,
        "mount_options": entry.mount_options,
        "node_config_id": machine.current_config_id,
    }
    device = block_devices[entry.on]
    if isinstance(device, models.Partition):
        params["partition"] = device
    else:
        params["block_device"] = device
    block_devices[entry.name] = models.Filesystem.objects.create(**params)


def _apply_layout_bcache(
    machine: models.Node, entry: StorageEntry, block_devices: List
):
    backing_device = block_devices[entry.backing_device]
    cache_device = block_devices[entry.cache_device]

    # track the cache device since multiple Bcaches can use the same cache
    # device
    cache_set_name = f"{entry.cache_device}[cacheset]"
    cache_set = block_devices.get(cache_set_name)
    if not cache_set:
        cache_set = models.CacheSet.objects.create()
        block_devices[cache_set_name] = cache_set
        params = {
            "fstype": FILESYSTEM_TYPE.BCACHE_CACHE,
            "cache_set": cache_set,
            "node_config_id": machine.current_config_id,
        }
        if isinstance(cache_device, models.Partition):
            params["partition"] = cache_device
        else:
            params["block_device"] = cache_device
        models.Filesystem.objects.create(**params)

    params = {
        "name": entry.name,
        "cache_mode": entry.cache_mode,
        "cache_set": cache_set,
    }
    if isinstance(backing_device, models.Partition):
        params["backing_partition"] = backing_device
    else:
        params["backing_device"] = backing_device
    bcache = models.Bcache.objects.create_bcache(**params)
    block_devices[entry.name] = bcache.virtual_device


def _apply_layout_lvm(
    machine: models.Node, entry: StorageEntry, block_devices: List
):
    devices = []
    partitions = []
    for name in entry.members:
        device = block_devices[name]
        if isinstance(device, models.Partition):
            partitions.append(device)
        else:
            devices.append(device)
    vg = models.VolumeGroup.objects.create_volume_group(
        entry.name, devices, partitions
    )
    block_devices[entry.name] = vg


def _apply_layout_logicalvolume(
    machine: models.Node, entry: StorageEntry, block_devices: List
):
    vg = block_devices[entry.on]
    lv = vg.create_logical_volume(entry.name, entry.size)
    block_devices[entry.name] = lv


def _apply_layout_raid(
    machine: models.Node, entry: StorageEntry, block_devices: List
):
    devices = []
    partitions = []
    spare_devices = []
    spare_partitions = []
    for name in entry.members:
        device = block_devices[name]
        if isinstance(device, models.Partition):
            partitions.append(device)
        else:
            devices.append(device)
    for name in entry.spares:
        device = block_devices[name]
        if isinstance(device, models.Partition):
            spare_partitions.append(device)
        else:
            spare_devices.append(device)
    raid = models.RAID.objects.create_raid(
        f"raid-{entry.level}",
        name=entry.name,
        block_devices=devices,
        partitions=partitions,
        spare_devices=spare_devices,
        spare_partitions=spare_partitions,
    )
    block_devices[entry.name] = raid.virtual_device


def _apply_layout_special_device(
    machine: models.Node, entry: StorageEntry, block_devices: List
):
    # there's no device linked to special filesystems
    block_devices[entry.name] = None


_LAYOUT_APPLIERS = {
    "BCache": _apply_layout_bcache,
    "Disk": _apply_layout_disk,
    "FileSystem": _apply_layout_filesystem,
    "Partition": _apply_layout_partition,
    "LogicalVolume": _apply_layout_logicalvolume,
    "LVM": _apply_layout_lvm,
    "RAID": _apply_layout_raid,
    "SpecialDevice": _apply_layout_special_device,
}


def _add_missing_disks(entries: List[StorageEntry]) -> List[StorageEntry]:
    known_names: Set[str] = set()
    deps_names: Set[str] = set()
    for entry in entries:
        known_names.add(entry.name)
        deps_names.update(entry.deps())
    missing_names = sorted(deps_names - known_names)
    entries.extend(Disk(name) for name in missing_names)
    return entries


def _get_storage_entries(config: Config) -> List[StorageEntry]:
    entries = _flatten(config)
    _add_missing_disks(entries)
    return entries


def _sort_entries(entries: List[StorageEntry]) -> List[StorageEntry]:
    sorted_entries = []
    already_sorted: Set[str] = set()
    entries = entries.copy()
    while entries:
        # iterate over a copy since entries might get removed during loop
        for entry in list(entries):
            if entry.deps() - already_sorted:
                continue
            entries.remove(entry)
            sorted_entries.append(entry)
            already_sorted.add(entry.name)

    return sorted_entries


def _set_mountpoints(entries: Dict[str, StorageEntry], config: Config):
    mounted_devices = set()  # all devices with a mountpoint
    for mount, data in config.items():
        device = data["device"]
        mounted_devices.add(device)
        try:
            fs = cast(FileSystem, entries[f"{device}[fs]"])
        except KeyError:
            raise ConfigError(f"Filesystem not found for device '{device}'")  # noqa: B904
        fs.mount = mount
        fs.mount_options = data.get("options", "")
    # all special filesystems must have a mount point
    special_devices = {
        entry.name
        for entry in entries.values()
        if isinstance(entry, SpecialDevice)
    }
    unmounted_devices = special_devices - mounted_devices
    if unmounted_devices:
        unmounted_list = ", ".join(sorted(unmounted_devices))
        raise ConfigError(
            f"Special device(s) missing mountpoint: {unmounted_list}"
        )


def _get_size(size: str) -> int:
    """Return size in bytes from a string.

    It supports M, G, T suffixes.
    """
    multipliers = {
        "M": 1000**2,
        "G": 1000**3,
        "T": 1000**4,
    }
    try:
        value, multiplier = size[:-1], size[-1]
        value = float(value)
        bytes_value = int(value * multipliers[multiplier])
    except (IndexError, KeyError, ValueError):
        raise ConfigError(f"Invalid size '{size}'")  # noqa: B904
    if bytes_value <= 0:
        raise ConfigError(f"Invalid negative size '{size}'")
    return bytes_value


def _validate_schema(data: Config):
    """Validate data against the JSON schema."""
    schema = yaml.safe_load(SCHEMA_FILE.read_text())
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        path = "/".join(str(item) for item in e.absolute_path)
        if not path:
            path = "top level"
        raise ConfigError(f"Invalid config at {path}: {e.message}")  # noqa: B904
