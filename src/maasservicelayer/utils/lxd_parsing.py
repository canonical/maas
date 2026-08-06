# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers to extract hardware profile data from LXD commissioning output."""

from collections import defaultdict
import re

from maascommon.fields import normalise_macaddress
from maascommon.storage import (
    is_virtual_bcache_holder,
    multipath_lun,
    parse_device_path,
)
from maasservicelayer.models.hardwareprofile import (
    HardwareAcceleratorGroup,
    HardwareAcceleratorItem,
    HardwareNetworkGroup,
    HardwareNetworkItem,
    HardwareStorageGroup,
    HardwareStorageItem,
)
from maasservicelayer.utils.lxd import (
    LXDCPU,
    LXDGPU,
    LXDMemory,
    LXDNetwork,
    LXDNetworkCardPort,
    LXDStorage,
    LXDStorageDisk,
    MachineResources,
)
from provisioningserver.utils.arch import kernel_to_debian_architecture

# MAAS doesn't model disks smaller than 4MiB.
MIN_BLOCK_DEVICE_SIZE = 4 * 1024 * 1024

# A regular MAC address is 17 characters long. Longer values come from IP over
# Infiniband devices, which MAAS doesn't model. See LP:1939456.
MAX_MAC_ADDRESS_LENGTH = 17

CPU_MODEL_SPEED_RE = re.compile(r"\s@\s(?P<ghz>\d+\.\d+)GHz$")


def parse_cpu(cpu: LXDCPU) -> tuple[int, int]:
    """Return the CPU core count and speed (MHz) from LXD CPU resources."""
    socket_names = [socket.name for socket in cpu.sockets if socket.name]

    cpu_speed = 0
    # Only trust the model name speed when all sockets are the same model.
    if socket_names and all(name == socket_names[0] for name in socket_names):
        match = CPU_MODEL_SPEED_RE.search(socket_names[0])
        if match:
            cpu_speed = int(float(match.group("ghz")) * 1000)

    # The model name doesn't always include the speed. Fall back to the max
    # turbo frequency, then to the average current frequency (which may be
    # affected by CPU scaling, so it's rounded to the nearest hundred).
    if not cpu_speed:
        max_turbo = max(
            (socket.frequency_turbo for socket in cpu.sockets), default=0
        )
        if max_turbo:
            cpu_speed = max_turbo
        elif cpu.sockets:
            average = sum(socket.frequency for socket in cpu.sockets) / len(
                cpu.sockets
            )
            if average:
                cpu_speed = round(average / 100) * 100

    return cpu.total, cpu_speed


def parse_memory_mb(memory: LXDMemory) -> int:
    return int(memory.total / 1024**2)


def interface_speed(port: LXDNetworkCardPort) -> int:
    """Return the highest speed (Mbit/s) the port supports."""
    if not port.supported_modes:
        return 0
    return max(int(mode.split("base")[0]) for mode in port.supported_modes)


def disk_id_path(device_id: str, serial: str, disk_id: str) -> str:
    """Return a stable device path, preferring the by-id link."""
    id_path = f"/dev/disk/by-id/{device_id}" if device_id else ""
    # No by-id link or no serial is a strong indicator of a virtual disk, so
    # fall back to the plain device path.
    if not device_id or not serial:
        id_path = f"/dev/{disk_id}"
    return id_path


def is_modelled_disk(disk: LXDStorageDisk) -> bool:
    if disk.read_only or disk.type == "cdrom":
        return False
    if disk.size <= MIN_BLOCK_DEVICE_SIZE:
        return False
    # bcache holders are stacked on disks already reported in the same list.
    if is_virtual_bcache_holder(disk.id):
        return False
    id_path = disk_id_path(disk.device_id, disk.serial, disk.id)
    # Loopback devices won't be available on the next boot.
    return not id_path.startswith("/dev/loop")


def condense_luns(disks: list[LXDStorageDisk]) -> list[LXDStorageDisk]:
    """Return one disk per LUN, dropping the redundant multipath paths.

    A multipath LUN is a single storage source reachable through several
    paths, and LXD reports one disk per path. MAAS models the source only,
    since curtin sets multipath up at deployment time.
    """
    lun_paths: dict[tuple[str, str], list[LXDStorageDisk]] = defaultdict(list)
    condensed = []
    for disk in disks:
        device_path = parse_device_path(disk.device_path)
        lun = multipath_lun(device_path) if device_path else None
        if lun and disk.serial:
            lun_paths[(disk.serial, lun)].append(disk)
        else:
            condensed.append(disk)

    for paths in lun_paths.values():
        paths.sort(key=lambda disk: disk.id)
        source = paths[0]
        if not source.device_id:
            # Only some of the paths may expose a by-id link.
            source = source.model_copy(
                update={
                    "device_id": next(
                        (path.device_id for path in paths if path.device_id),
                        "",
                    )
                }
            )
        condensed.append(source)

    return sorted(condensed, key=lambda disk: disk.id)


def parse_storage(storage: LXDStorage) -> list[HardwareStorageGroup]:
    groups: dict[tuple[str, int], list[HardwareStorageItem]] = defaultdict(
        list
    )
    for disk in condense_luns(storage.disks):
        if not is_modelled_disk(disk):
            continue
        groups[(disk.type, disk.size)].append(
            HardwareStorageItem(
                name=disk.id,
                size_bytes=disk.size,
                block_size=disk.block_size or 512,
                id_path=disk_id_path(disk.device_id, disk.serial, disk.id),
                model=disk.model or None,
                serial=disk.serial or None,
                firmware_version=disk.firmware_version or None,
                numa_node=disk.numa_node,
            )
        )
    return [
        HardwareStorageGroup(
            disk_type=disk_type,
            size_bytes=size_bytes,
            count=len(items),
            items=items,
        )
        for (disk_type, size_bytes), items in groups.items()
    ]


def parse_network(network: LXDNetwork) -> list[HardwareNetworkGroup]:
    groups: dict[tuple[str, str, str, str, int], list[HardwareNetworkItem]] = (
        defaultdict(list)
    )
    for card in network.cards:
        sriov_max_vf = card.sriov.maximum_vfs if card.sriov else 0
        for port in card.ports:
            mac = port.address
            if not mac or len(mac) > MAX_MAC_ADDRESS_LENGTH:
                continue
            item = HardwareNetworkItem(
                name=port.id,
                mac_address=normalise_macaddress(mac),
                link_speed=port.link_speed,
                sriov_max_vf=sriov_max_vf,
                numa_node=card.numa_node,
            )
            key = (
                card.vendor_id,
                card.product_id,
                card.vendor,
                card.product,
                interface_speed(port),
            )
            groups[key].append(item)
    return [
        HardwareNetworkGroup(
            speed_mbps=speed_mbps,
            vendor_id=vendor_id,
            product_id=product_id,
            vendor=vendor,
            product=product,
            count=len(items),
            items=items,
        )
        for (
            vendor_id,
            product_id,
            vendor,
            product,
            speed_mbps,
        ), items in groups.items()
    ]


def parse_accelerators(gpu: LXDGPU) -> list[HardwareAcceleratorGroup]:
    groups: dict[tuple[str, str, str, str], list[HardwareAcceleratorItem]] = (
        defaultdict(list)
    )
    for card in gpu.cards:
        sriov_max_vf = card.sriov.maximum_vfs if card.sriov else 0
        groups[
            (card.vendor_id, card.product_id, card.vendor, card.product)
        ].append(
            HardwareAcceleratorItem(
                pci_address=card.pci_address,
                numa_node=card.numa_node,
                sriov_max_vf=sriov_max_vf,
            )
        )
    return [
        HardwareAcceleratorGroup(
            vendor_id=vendor_id,
            product_id=product_id,
            vendor=vendor,
            product=product,
            count=len(items),
            items=items,
        )
        for (vendor_id, product_id, vendor, product), items in groups.items()
    ]


def parse_architecture(machine_resources: MachineResources) -> str:
    architecture = kernel_to_debian_architecture(
        machine_resources.environment.kernel_architecture
    )
    machine_extra = machine_resources.machine_extra
    if machine_extra and machine_extra.platform:
        arch = architecture.split("/", 1)[0]
        architecture = f"{arch}/{machine_extra.platform}"
    return architecture
