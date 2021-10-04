# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Parse format for custom storage configuration."""


import dataclasses
from typing import Any, cast, Dict, List, Optional, Set


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
    size: str
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


Config = Dict[str, Any]


def get_storage_layout(config: Config) -> StorageLayout:
    """Return a StorageLayout for the provided configuration."""
    entries = _get_storage_entries(config["layout"])
    entries_map = {entry.name: entry for entry in entries}
    _set_mountpoints(entries_map, config["mounts"])
    sorted_entries = _sort_entries(entries)
    return StorageLayout(entries=entries_map, sorted_entries=sorted_entries)


def _get_filesystem(name: str, data: Config) -> Optional[FileSystem]:
    fs = data.get("fs")
    if not fs:
        return None

    return FileSystem(
        name=f"{name}[fs]",
        on=name,
        type=fs,
    )


def _flatten_disk(name: str, data: Config) -> List[StorageEntry]:
    items: List = [Disk(name=name, ptable=data.get("ptable", ""))]
    items.extend(_disk_partitions(name, data.get("partitions", [])))
    return items


def _flatten_raid(name: str, data: Config) -> List[StorageEntry]:
    items: List = [
        RAID(
            name=name,
            level=data["level"],
            members=data.get("members", []),
            ptable=data.get("ptable", ""),
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
                size=volume["size"],
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
                size=part["size"],
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
        flattener = _FLATTENERS.get(data["type"])
        if flattener:
            items.extend(flattener(name, data))
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
        fs = cast(FileSystem, entries[f"{data['device']}[fs]"])
        fs.mount = mount
        fs.mount_options = data.get("options", "")
