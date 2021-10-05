# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Parse format for custom storage configuration."""


import dataclasses
from typing import Any, cast, Dict, List, Optional, Set

from maasserver.enum import (
    FILESYSTEM_TYPE_CHOICES,
    PARTITION_TABLE_TYPE_CHOICES,
)


@dataclasses.dataclass
class StorageEntry:
    name: str

    def deps(self) -> Set[str]:
        return set()


@dataclasses.dataclass
class StorageLayout:
    entries: Dict[str, StorageEntry]
    sorted_entries: List[StorageEntry]


@dataclasses.dataclass
class Disk(StorageEntry):
    ptable: str = ""


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
    ptable: str = ""

    def deps(self) -> Set[str]:
        return set(self.members)


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

    def deps(self) -> Set[str]:
        return {self.backing_device, self.cache_device}


class ConfigError(Exception):
    """Provided configuration is invalid."""


Config = Dict[str, Any]


def get_storage_layout(config: Config) -> StorageLayout:
    """Return a StorageLayout for the provided configuration."""
    for base_key in ("layout", "mounts"):
        if base_key not in config:
            raise ConfigError(f"Section '{base_key}' missing in config")
    entries = _get_storage_entries(config["layout"])
    entries_map = {entry.name: entry for entry in entries}
    _set_mountpoints(entries_map, config["mounts"])
    sorted_entries = _sort_entries(entries)
    return StorageLayout(entries=entries_map, sorted_entries=sorted_entries)


def _get_filesystem(name: str, data: Config) -> Optional[FileSystem]:
    fs = data.get("fs")
    if not fs:
        return None
    if fs not in (choice[0] for choice in FILESYSTEM_TYPE_CHOICES):
        raise ConfigError(f"Unknown filesystem type '{fs}'")
    return FileSystem(
        name=f"{name}[fs]",
        on=name,
        type=fs,
    )


def _validate_partition_table(name: str, data: Config) -> str:
    ptable = data.get("ptable", "")
    if ptable:
        if ptable.upper() not in (
            choice[0] for choice in PARTITION_TABLE_TYPE_CHOICES
        ):
            raise ConfigError(f"Unknown partition table type '{ptable}'")
    elif data.get("partitions"):
        raise ConfigError(f"Partition table not specified for '{name}'")
    return ptable


def _flatten_disk(name: str, data: Config) -> List[StorageEntry]:
    ptable = _validate_partition_table(name, data)
    items: List = [Disk(name=name, ptable=ptable)]
    items.extend(_disk_partitions(name, data.get("partitions", [])))
    return items


def _flatten_raid(name: str, data: Config) -> List[StorageEntry]:
    ptable = _validate_partition_table(name, data)
    items: List = [
        RAID(
            name=name,
            level=data["level"],
            members=data.get("members", []),
            ptable=ptable,
        )
    ]
    fs = _get_filesystem(name, data)
    if fs:
        items.append(fs)
    items.extend(_disk_partitions(name, data.get("partitions", [])))
    return items


def _flatten_bcache(name: str, data: Config) -> List[StorageEntry]:
    items: List = [
        BCache(
            name=name,
            backing_device=data["backing-device"],
            cache_device=data["cache-device"],
        )
    ]
    fs = _get_filesystem(name, data)
    if fs:
        items.append(fs)
    return items


def _flatten_lvm(name: str, data: Config) -> List[StorageEntry]:
    items: List = [
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


def _disk_partitions(
    disk_name: str, partitions_data: List[Config]
) -> List[StorageEntry]:
    items: List = []
    after = ""
    for part in partitions_data:
        part_name = part["name"]
        items.append(
            Partition(
                name=part_name,
                on=disk_name,
                size=_get_size(part["size"]),
                after=after,
            )
        )
        after = part_name
        fs = _get_filesystem(part_name, part)
        if fs:
            items.append(fs)
    return items


_FLATTENERS = {
    "disk": _flatten_disk,
    "raid": _flatten_raid,
    "bcache": _flatten_bcache,
    "lvm": _flatten_lvm,
}


def _flatten(config: Config) -> List[StorageEntry]:
    items: List[StorageEntry] = []
    for name, data in config.items():
        try:
            device_type = data["type"]
            flattener = _FLATTENERS[device_type]
        except KeyError:
            raise ConfigError(f"Unsupported device type '{device_type}'")

        try:
            items.extend(flattener(name, data))
        except KeyError as e:
            key = e.args[0]
            raise ConfigError(f"Missing required key '{key}' for '{name}'")
    return items


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
    for mount, data in config.items():
        device = data["device"]
        try:
            fs = cast(FileSystem, entries[f"{device}[fs]"])
        except KeyError:
            raise ConfigError(f"Filesystem not found for device '{device}'")
        fs.mount = mount
        fs.mount_options = data.get("options", "")


def _get_size(size: str) -> int:
    """Return size in bytes from a string.

    It supports M, G, T suffixes.
    """
    multipliers = {
        "M": 1000 ** 2,
        "G": 1000 ** 3,
        "T": 1000 ** 4,
    }
    try:
        value, multiplier = size[:-1], size[-1]
        value = float(value)
        bytes_value = int(value * multipliers[multiplier])
    except (IndexError, KeyError, ValueError):
        raise ConfigError(f"Invalid size '{size}'")
    if bytes_value <= 0:
        raise ConfigError(f"Invalid negative size '{size}'")
    return bytes_value
