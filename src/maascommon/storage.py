# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers to interpret the storage device information reported by LXD."""

import re
from typing import NamedTuple

# Multipath devices expose the same LUN through several paths. The path
# component of a `/dev/disk/by-path` link encodes the LUN differently per
# transport protocol, so each one needs its own pattern.
_MULTIPATH_LUN_RES = {
    "fc": [re.compile(r"^(?P<port>\w+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$")],
    "vmbus": [re.compile(r"^(?P<guid>\w+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$")],
    "sas": [
        re.compile(
            r"^(?P<sas_addr>0x[\da-fA-F]+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$"
        ),
        re.compile(
            r"^exp0x[\da-fA-F]+-phy(?P<phy_id>(0x)?[\da-fA-F]+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$"
        ),
        re.compile(
            r"^phy(?P<phy_id>(0x)?[\da-fA-F]+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$"
        ),
    ],
    "ip": [
        re.compile(
            r"^[\.\-\w:]+-iscsi-(?P<target>[\.\-\w:]+)-(?P<lun>lun-(0x)?[\da-fA-F]+)$"
        )
    ],
}

_DEVICE_PATH_RE = re.compile(
    r"^(?P<bus>\w+)-(?P<bus_addr>[\da-fA-F:\.]+)-(?P<proto>\w+)-(?P<device>.*)$"
)


class DevicePath(NamedTuple):
    bus: str
    bus_address: str
    protocol: str
    device: str


def parse_device_path(device_path: str) -> DevicePath | None:
    """Split a `/dev/disk/by-path` name into its components."""
    match = _DEVICE_PATH_RE.match(device_path)
    if match is None:
        return None
    return DevicePath(
        bus=match["bus"],
        bus_address=match["bus_addr"],
        protocol=match["proto"],
        device=match["device"],
    )


def multipath_lun(device_path: DevicePath) -> str | None:
    """Return the LUN this path points at, or None if it isn't a LUN path.

    USB is excluded because it never carries multipath devices.
    """
    if device_path.protocol == "usb":
        return None
    for lun_re in _MULTIPATH_LUN_RES.get(device_path.protocol, []):
        if match := lun_re.match(device_path.device):
            return match["lun"]
    return None


def is_virtual_bcache_holder(disk_id: str) -> bool:
    """Whether the disk is a bcache holder rather than a physical disk.

    bcache virtual holder devices are always named "bcacheN" by the kernel
    (e.g. /dev/bcache0). This name comes from the "id" LXD reports for a
    disk, which is just the /sys/class/block/<name> directory name assigned
    by the originating kernel driver at registration time. It cannot be
    overridden by users. LXD reports bcache holders alongside physical
    disks in the "storage.disks" list, but they are stacked virtual devices
    backed by other disks that are already present in the same list.
    """
    return disk_id.startswith("bcache")
